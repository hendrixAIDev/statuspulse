-- StatusPulse Database Schema
-- Run this in Supabase SQL Editor

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table (extends Supabase auth.users)
CREATE TABLE public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    display_name TEXT,
    plan TEXT NOT NULL DEFAULT 'free' CHECK (plan IN ('free', 'pro')),
    max_monitors INTEGER NOT NULL DEFAULT 3,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Monitors table
CREATE TABLE public.monitors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    method TEXT NOT NULL DEFAULT 'GET' CHECK (method IN ('GET', 'HEAD', 'POST')),
    expected_status INTEGER NOT NULL DEFAULT 200,
    check_interval_seconds INTEGER NOT NULL DEFAULT 300, -- 5 min default
    timeout_seconds INTEGER NOT NULL DEFAULT 30,
    is_active BOOLEAN NOT NULL DEFAULT true,
    current_status TEXT NOT NULL DEFAULT 'unknown' CHECK (current_status IN ('up', 'down', 'unknown', 'paused')),
    last_checked_at TIMESTAMPTZ,
    last_status_change_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Check results table (partitioned by time for performance)
CREATE TABLE public.checks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    monitor_id UUID NOT NULL REFERENCES public.monitors(id) ON DELETE CASCADE,
    status_code INTEGER,
    response_time_ms INTEGER,
    is_up BOOLEAN NOT NULL,
    error_message TEXT,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create index for fast lookups
CREATE INDEX idx_checks_monitor_time ON public.checks(monitor_id, checked_at DESC);
CREATE INDEX idx_checks_checked_at ON public.checks(checked_at DESC);

-- Incidents table (tracks downtime periods)
CREATE TABLE public.incidents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    monitor_id UUID NOT NULL REFERENCES public.monitors(id) ON DELETE CASCADE,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    duration_seconds INTEGER,
    cause TEXT,
    is_resolved BOOLEAN NOT NULL DEFAULT false
);

CREATE INDEX idx_incidents_monitor ON public.incidents(monitor_id, started_at DESC);

-- Alert configurations
CREATE TABLE public.alert_configs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    monitor_id UUID NOT NULL REFERENCES public.monitors(id) ON DELETE CASCADE,
    alert_type TEXT NOT NULL CHECK (alert_type IN ('email', 'webhook', 'slack')),
    destination TEXT NOT NULL, -- email address or webhook URL
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Alert history
CREATE TABLE public.alert_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    alert_config_id UUID REFERENCES public.alert_configs(id) ON DELETE SET NULL,
    monitor_id UUID NOT NULL REFERENCES public.monitors(id) ON DELETE CASCADE,
    alert_type TEXT NOT NULL,
    message TEXT NOT NULL,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    was_successful BOOLEAN NOT NULL DEFAULT true
);

-- Public status pages
CREATE TABLE public.status_pages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    slug TEXT NOT NULL UNIQUE, -- e.g., "my-company" for statuspulse.app/s/my-company
    title TEXT NOT NULL DEFAULT 'Status Page',
    description TEXT,
    is_public BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Status page monitors (which monitors appear on which status page)
CREATE TABLE public.status_page_monitors (
    status_page_id UUID NOT NULL REFERENCES public.status_pages(id) ON DELETE CASCADE,
    monitor_id UUID NOT NULL REFERENCES public.monitors(id) ON DELETE CASCADE,
    display_order INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (status_page_id, monitor_id)
);

-- Row Level Security
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.monitors ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.checks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.incidents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.alert_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.alert_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.status_pages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.status_page_monitors ENABLE ROW LEVEL SECURITY;

-- RLS Policies
-- Profiles: users can only see/edit their own
CREATE POLICY "Users can view own profile" ON public.profiles FOR SELECT USING (auth.uid() = id);
CREATE POLICY "Users can update own profile" ON public.profiles FOR UPDATE USING (auth.uid() = id);

-- Monitors: users can only see/edit their own
CREATE POLICY "Users can view own monitors" ON public.monitors FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can create monitors" ON public.monitors FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own monitors" ON public.monitors FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete own monitors" ON public.monitors FOR DELETE USING (auth.uid() = user_id);

-- Checks: users can view checks for their monitors
CREATE POLICY "Users can view own checks" ON public.checks FOR SELECT 
    USING (monitor_id IN (SELECT id FROM public.monitors WHERE user_id = auth.uid()));

-- Incidents: users can view incidents for their monitors
CREATE POLICY "Users can view own incidents" ON public.incidents FOR SELECT 
    USING (monitor_id IN (SELECT id FROM public.monitors WHERE user_id = auth.uid()));

-- Alert configs: users can manage alerts for their monitors
CREATE POLICY "Users can view own alerts" ON public.alert_configs FOR SELECT 
    USING (monitor_id IN (SELECT id FROM public.monitors WHERE user_id = auth.uid()));
CREATE POLICY "Users can create alerts" ON public.alert_configs FOR INSERT 
    WITH CHECK (monitor_id IN (SELECT id FROM public.monitors WHERE user_id = auth.uid()));
CREATE POLICY "Users can update own alerts" ON public.alert_configs FOR UPDATE 
    USING (monitor_id IN (SELECT id FROM public.monitors WHERE user_id = auth.uid()));
CREATE POLICY "Users can delete own alerts" ON public.alert_configs FOR DELETE 
    USING (monitor_id IN (SELECT id FROM public.monitors WHERE user_id = auth.uid()));

-- Status pages: owners can manage, public ones are viewable by all
CREATE POLICY "Users can view own status pages" ON public.status_pages FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Public status pages are viewable" ON public.status_pages FOR SELECT USING (is_public = true);
CREATE POLICY "Users can create status pages" ON public.status_pages FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own status pages" ON public.status_pages FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete own status pages" ON public.status_pages FOR DELETE USING (auth.uid() = user_id);

-- Functions
-- Auto-create profile on user signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, email, display_name)
    VALUES (NEW.id, NEW.email, COALESCE(NEW.raw_user_meta_data->>'display_name', split_part(NEW.email, '@', 1)));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Function to calculate uptime percentage for a monitor
CREATE OR REPLACE FUNCTION public.get_uptime_percentage(
    p_monitor_id UUID,
    p_days INTEGER DEFAULT 30
)
RETURNS NUMERIC AS $$
DECLARE
    total_checks INTEGER;
    up_checks INTEGER;
BEGIN
    SELECT COUNT(*), COUNT(*) FILTER (WHERE is_up = true)
    INTO total_checks, up_checks
    FROM public.checks
    WHERE monitor_id = p_monitor_id
    AND checked_at > NOW() - (p_days || ' days')::INTERVAL;
    
    IF total_checks = 0 THEN
        RETURN 100.0;
    END IF;
    
    RETURN ROUND((up_checks::NUMERIC / total_checks::NUMERIC) * 100, 2);
END;
$$ LANGUAGE plpgsql;

-- Cleanup old checks (keep 90 days for pro, 7 for free)
CREATE OR REPLACE FUNCTION public.cleanup_old_checks()
RETURNS void AS $$
BEGIN
    -- Delete checks older than 90 days for all users
    DELETE FROM public.checks 
    WHERE checked_at < NOW() - INTERVAL '90 days';
    
    -- Delete checks older than 7 days for free users
    DELETE FROM public.checks 
    WHERE checked_at < NOW() - INTERVAL '7 days'
    AND monitor_id IN (
        SELECT m.id FROM public.monitors m
        JOIN public.profiles p ON m.user_id = p.id
        WHERE p.plan = 'free'
    );
END;
$$ LANGUAGE plpgsql;
