/**
 * StatusPulse — Cloudflare Worker (Monitoring Engine)
 * 
 * Replaces the Mac mini LaunchAgent daemon with distributed, always-on monitoring.
 * Runs on Cloudflare's edge network via Cron Triggers.
 * 
 * Environment Variables (set in wrangler.jsonc or dashboard):
 *   SUPABASE_URL       - Supabase project URL
 *   SUPABASE_SERVICE_KEY - Supabase service role key (bypasses RLS)
 *   SMTP_EMAIL         - (optional) Gmail address for email alerts
 *   SMTP_PASSWORD      - (optional) Gmail app password
 * 
 * Cron schedule: every 5 minutes (free tier) or every 1 minute (paid)
 */

export default {
  /**
   * Cron Trigger handler — runs monitoring checks on schedule.
   */
  async scheduled(controller, env, ctx) {
    const startTime = Date.now();
    
    try {
      const results = await runAllChecks(env);
      const elapsed = Date.now() - startTime;
      
      console.log(`[StatusPulse] Checked ${results.length} monitors in ${elapsed}ms`);
      for (const r of results) {
        const status = r.is_up ? 'UP' : 'DOWN';
        console.log(`  ${r.monitor_name}: ${status} (${r.response_time_ms ?? 'N/A'}ms)`);
      }
    } catch (err) {
      console.error(`[StatusPulse] Monitoring cycle failed:`, err.message);
    }
  },

  /**
   * HTTP handler — for manual triggers and health checks.
   * GET /           → Health check
   * POST /check     → Manually trigger all checks
   * GET /status     → Return current monitor statuses as JSON
   */
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    
    // Health check
    if (url.pathname === '/' && request.method === 'GET') {
      return new Response(JSON.stringify({
        service: 'StatusPulse Monitor Worker',
        status: 'healthy',
        timestamp: new Date().toISOString(),
        region: request.cf?.colo || 'unknown'
      }), {
        headers: { 'Content-Type': 'application/json' }
      });
    }
    
    // Manual trigger (requires auth)
    if (url.pathname === '/check' && request.method === 'POST') {
      const authHeader = request.headers.get('Authorization');
      if (authHeader !== `Bearer ${env.SUPABASE_SERVICE_KEY}`) {
        return new Response('Unauthorized', { status: 401 });
      }
      
      const results = await runAllChecks(env);
      return new Response(JSON.stringify({ checked: results.length, results }), {
        headers: { 'Content-Type': 'application/json' }
      });
    }
    
    // Current status (public read-only, returns only monitor names and status — no URLs)
    if (url.pathname === '/status' && request.method === 'GET') {
      const monitors = await getActiveMonitors(env);
      const summary = monitors.map(m => ({
        name: m.name,
        status: m.current_status,
        last_checked: m.last_checked_at
      }));
      return new Response(JSON.stringify({ monitors: summary }), {
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*',
          'Cache-Control': 'public, max-age=60'
        }
      });
    }
    
    return new Response('Not Found', { status: 404 });
  }
};


// ─── Core Monitoring Logic ──────────────────────────────────────────────────

/**
 * Fetch all active monitors from Supabase.
 */
async function getActiveMonitors(env) {
  const res = await fetch(
    `${env.SUPABASE_URL}/rest/v1/monitors?is_active=eq.true&select=*`,
    {
      headers: {
        'apikey': env.SUPABASE_SERVICE_KEY,
        'Authorization': `Bearer ${env.SUPABASE_SERVICE_KEY}`,
        'Content-Type': 'application/json'
      }
    }
  );
  
  if (!res.ok) {
    throw new Error(`Failed to fetch monitors: ${res.status} ${await res.text()}`);
  }
  
  return await res.json();
}

/**
 * Check a single URL and return the result.
 */
async function checkUrl(url, method = 'GET', expectedStatus = 200, timeoutMs = 30000) {
  const result = {
    url,
    is_up: false,
    status_code: null,
    response_time_ms: null,
    error_message: null,
    checked_at: new Date().toISOString()
  };
  
  try {
    const abortCtrl = new AbortController();
    const timeoutId = setTimeout(() => abortCtrl.abort(), timeoutMs);
    
    // Use 'manual' redirect mode when we expect a redirect status (3xx).
    // This prevents redirect loops (e.g., Streamlit Cloud's auth flow
    // which requires cookies that Workers' fetch() doesn't maintain).
    const isRedirectExpected = expectedStatus >= 300 && expectedStatus < 400;
    
    const start = Date.now();
    const response = await fetch(url, {
      method: method === 'HEAD' ? 'HEAD' : method === 'POST' ? 'POST' : 'GET',
      signal: abortCtrl.signal,
      redirect: isRedirectExpected ? 'manual' : 'follow',
      headers: {
        'User-Agent': 'StatusPulse/1.0 (https://statuspulse.dev)'
      }
    });
    const elapsed = Date.now() - start;
    
    clearTimeout(timeoutId);
    
    result.status_code = response.status;
    result.response_time_ms = elapsed;
    result.is_up = response.status === expectedStatus;
    
    if (!result.is_up) {
      result.error_message = `Expected ${expectedStatus}, got ${response.status}`;
    }
  } catch (err) {
    if (err.name === 'AbortError') {
      result.error_message = `Timeout after ${timeoutMs / 1000}s`;
    } else {
      result.error_message = `Error: ${err.message}`.slice(0, 200);
    }
  }
  
  return result;
}

/**
 * Save a check result to Supabase.
 */
async function saveCheckResult(env, monitorId, result) {
  const res = await fetch(
    `${env.SUPABASE_URL}/rest/v1/checks`,
    {
      method: 'POST',
      headers: {
        'apikey': env.SUPABASE_SERVICE_KEY,
        'Authorization': `Bearer ${env.SUPABASE_SERVICE_KEY}`,
        'Content-Type': 'application/json',
        'Prefer': 'return=minimal'
      },
      body: JSON.stringify({
        monitor_id: monitorId,
        status_code: result.status_code,
        response_time_ms: result.response_time_ms,
        is_up: result.is_up,
        error_message: result.error_message,
        checked_at: result.checked_at
      })
    }
  );
  
  if (!res.ok) {
    console.error(`Failed to save check for ${monitorId}: ${res.status}`);
  }
}

/**
 * Update monitor status and handle incidents/alerts.
 */
async function updateMonitorStatus(env, monitor, isUp) {
  const oldStatus = monitor.current_status;
  const newStatus = isUp ? 'up' : 'down';
  const now = new Date().toISOString();
  
  // Build update payload
  const updateData = {
    current_status: newStatus,
    last_checked_at: now,
    updated_at: now
  };
  
  // Detect status change
  const statusChanged = oldStatus !== newStatus && oldStatus !== 'unknown';
  
  if (statusChanged) {
    updateData.last_status_change_at = now;
    
    if (newStatus === 'down') {
      // Create incident
      await supabasePost(env, 'incidents', {
        monitor_id: monitor.id,
        started_at: now,
        is_resolved: false
      });
      
      // Send down alerts
      await sendAlerts(env, monitor, 'down');
      
    } else if (newStatus === 'up' && oldStatus === 'down') {
      // Resolve open incidents
      await resolveIncidents(env, monitor.id, now);
      
      // Send recovery alerts
      await sendAlerts(env, monitor, 'up');
    }
  }
  
  // Update monitor record
  await fetch(
    `${env.SUPABASE_URL}/rest/v1/monitors?id=eq.${monitor.id}`,
    {
      method: 'PATCH',
      headers: {
        'apikey': env.SUPABASE_SERVICE_KEY,
        'Authorization': `Bearer ${env.SUPABASE_SERVICE_KEY}`,
        'Content-Type': 'application/json',
        'Prefer': 'return=minimal'
      },
      body: JSON.stringify(updateData)
    }
  );
}

/**
 * Resolve all open incidents for a monitor.
 */
async function resolveIncidents(env, monitorId, now) {
  // Get open incidents
  const res = await fetch(
    `${env.SUPABASE_URL}/rest/v1/incidents?monitor_id=eq.${monitorId}&is_resolved=eq.false&select=*`,
    {
      headers: {
        'apikey': env.SUPABASE_SERVICE_KEY,
        'Authorization': `Bearer ${env.SUPABASE_SERVICE_KEY}`,
        'Content-Type': 'application/json'
      }
    }
  );
  
  if (!res.ok) return;
  const incidents = await res.json();
  
  for (const incident of incidents) {
    const started = new Date(incident.started_at);
    const duration = Math.floor((new Date(now) - started) / 1000);
    
    await fetch(
      `${env.SUPABASE_URL}/rest/v1/incidents?id=eq.${incident.id}`,
      {
        method: 'PATCH',
        headers: {
          'apikey': env.SUPABASE_SERVICE_KEY,
          'Authorization': `Bearer ${env.SUPABASE_SERVICE_KEY}`,
          'Content-Type': 'application/json',
          'Prefer': 'return=minimal'
        },
        body: JSON.stringify({
          resolved_at: now,
          duration_seconds: duration,
          is_resolved: true
        })
      }
    );
  }
}

/**
 * Send alerts for a monitor status change.
 */
async function sendAlerts(env, monitor, status) {
  // Get alert configs
  const res = await fetch(
    `${env.SUPABASE_URL}/rest/v1/alert_configs?monitor_id=eq.${monitor.id}&is_active=eq.true&select=*`,
    {
      headers: {
        'apikey': env.SUPABASE_SERVICE_KEY,
        'Authorization': `Bearer ${env.SUPABASE_SERVICE_KEY}`,
        'Content-Type': 'application/json'
      }
    }
  );
  
  if (!res.ok) return;
  const alerts = await res.json();
  
  for (const alert of alerts) {
    try {
      if (alert.alert_type === 'webhook') {
        await sendWebhookAlert(alert, monitor, status);
      }
      // Note: Email alerts from Workers requires a third-party service
      // (Cloudflare Workers can't do SMTP directly — use Mailgun, Resend, or similar)
      // For now, email alerts continue to work via the fallback daemon or a separate email service
      
      // Log success
      await supabasePost(env, 'alert_history', {
        alert_config_id: alert.id,
        monitor_id: monitor.id,
        alert_type: alert.alert_type,
        message: `${monitor.name} is ${status.toUpperCase()}`,
        was_successful: true
      });
      
    } catch (err) {
      // Log failure
      await supabasePost(env, 'alert_history', {
        alert_config_id: alert.id,
        monitor_id: monitor.id,
        alert_type: alert.alert_type,
        message: `Failed: ${err.message}`.slice(0, 200),
        was_successful: false
      });
    }
  }
}

/**
 * Send a webhook alert.
 */
async function sendWebhookAlert(alertConfig, monitor, status) {
  await fetch(alertConfig.destination, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      event: 'monitor_status_changed',
      monitor: {
        name: monitor.name,
        url: monitor.url,
        status: status
      },
      timestamp: new Date().toISOString()
    }),
    signal: AbortSignal.timeout(10000)
  });
}

/**
 * Helper to POST to Supabase.
 */
async function supabasePost(env, table, data) {
  return fetch(
    `${env.SUPABASE_URL}/rest/v1/${table}`,
    {
      method: 'POST',
      headers: {
        'apikey': env.SUPABASE_SERVICE_KEY,
        'Authorization': `Bearer ${env.SUPABASE_SERVICE_KEY}`,
        'Content-Type': 'application/json',
        'Prefer': 'return=minimal'
      },
      body: JSON.stringify(data)
    }
  );
}

/**
 * Run checks for all active monitors that are due.
 */
async function runAllChecks(env) {
  const monitors = await getActiveMonitors(env);
  const results = [];
  const now = Date.now();
  
  // Filter monitors that are due for checking
  const dueMonitors = monitors.filter(m => {
    if (!m.last_checked_at) return true;
    const lastCheck = new Date(m.last_checked_at).getTime();
    const elapsed = (now - lastCheck) / 1000;
    return elapsed >= m.check_interval_seconds;
  });
  
  // Run checks in parallel (Cloudflare allows up to 6 simultaneous connections on free,
  // but we batch to avoid hitting subrequest limits)
  const batchSize = 10;
  for (let i = 0; i < dueMonitors.length; i += batchSize) {
    const batch = dueMonitors.slice(i, i + batchSize);
    
    const batchResults = await Promise.allSettled(
      batch.map(async (monitor) => {
        const result = await checkUrl(
          monitor.url,
          monitor.method,
          monitor.expected_status,
          monitor.timeout_seconds * 1000
        );
        
        // Save result and update status in parallel
        await Promise.all([
          saveCheckResult(env, monitor.id, result),
          updateMonitorStatus(env, monitor, result.is_up)
        ]);
        
        return {
          monitor_name: monitor.name,
          ...result
        };
      })
    );
    
    for (const r of batchResults) {
      if (r.status === 'fulfilled') {
        results.push(r.value);
      } else {
        console.error('Check failed:', r.reason);
      }
    }
  }
  
  return results;
}
