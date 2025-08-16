-- Create problems table
CREATE TABLE IF NOT EXISTS public.problems (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    statement TEXT NOT NULL,
    solution TEXT DEFAULT '',
    has_negative_reviews BOOLEAN DEFAULT FALSE,
    review_url TEXT DEFAULT '',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create sources table
CREATE TABLE IF NOT EXISTS public.sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    snippet TEXT DEFAULT '',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create junction table for problems and sources
CREATE TABLE IF NOT EXISTS public.problem_sources (
    problem_id UUID NOT NULL REFERENCES public.problems(id) ON DELETE CASCADE,
    source_id UUID NOT NULL REFERENCES public.sources(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (problem_id, source_id)
);

-- Create index on problem statement for faster lookups
CREATE INDEX IF NOT EXISTS idx_problems_statement ON public.problems(statement);

-- Create index on source URL for faster lookups
CREATE INDEX IF NOT EXISTS idx_sources_url ON public.sources(url);

-- Create RLS policies
-- Enable row level security
ALTER TABLE public.problems ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.problem_sources ENABLE ROW LEVEL SECURITY;

-- Create policy for anonymous access (read-only)
CREATE POLICY "Allow anonymous select" ON public.problems FOR SELECT USING (true);
CREATE POLICY "Allow anonymous select" ON public.sources FOR SELECT USING (true);
CREATE POLICY "Allow anonymous select" ON public.problem_sources FOR SELECT USING (true);

-- Create functions for getting problems with their sources
CREATE OR REPLACE FUNCTION public.get_problems_with_sources()
RETURNS TABLE (
    id UUID,
    statement TEXT,
    solution TEXT,
    has_negative_reviews BOOLEAN,
    review_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE,
    sources JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        p.id,
        p.statement,
        p.solution,
        p.has_negative_reviews,
        p.review_url,
        p.created_at,
        p.updated_at,
        (
            SELECT jsonb_agg(
                jsonb_build_object(
                    'id', s.id,
                    'title', s.title,
                    'url', s.url,
                    'snippet', s.snippet
                )
            )
            FROM public.problem_sources ps
            JOIN public.sources s ON ps.source_id = s.id
            WHERE ps.problem_id = p.id
        ) AS sources
    FROM public.problems p
    ORDER BY p.updated_at DESC;
END;
$$ LANGUAGE plpgsql;
