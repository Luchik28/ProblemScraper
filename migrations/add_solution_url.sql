-- Alter table to add solution_url column
ALTER TABLE problems
ADD COLUMN IF NOT EXISTS solution_url text;

-- Update RLS policies to include solution_url
ALTER POLICY "Enable read access for all users" ON public.problems
USING (true);

ALTER POLICY "Enable insert for authenticated users only" ON public.problems
FOR INSERT
WITH CHECK (auth.role() = 'authenticated');

ALTER POLICY "Enable update for authenticated users only" ON public.problems
FOR UPDATE
USING (auth.role() = 'authenticated')
WITH CHECK (auth.role() = 'authenticated');
