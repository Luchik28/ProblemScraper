import { supabase } from '@/lib/supabase';
import { Problem } from '@/types';

export async function getProblems(): Promise<Problem[]> {
  try {
    // Use the stored procedure to get problems with their sources
    const { data, error } = await supabase
      .rpc('get_problems_with_sources');

    if (error) throw error;
    
    return data as Problem[];
  } catch (error) {
    console.error('Error fetching problems:', error);
    return [];
  }
}

export async function getProblemById(id: string): Promise<Problem | null> {
  try {
    // Get the problem by id
    const { data: problem, error: problemError } = await supabase
      .from('problems')
      .select('*')
      .eq('id', id)
      .single();

    if (problemError) throw problemError;
    if (!problem) return null;

    // Get the sources for this problem
    const { data: sources, error: sourcesError } = await supabase
      .from('problem_sources')
      .select(`
        sources:source_id (
          id,
          title,
          url,
          snippet
        )
      `)
      .eq('problem_id', id);

    if (sourcesError) throw sourcesError;

    // Format the result
    return {
      ...problem,
      sources: sources?.map(item => item.sources) || []
    } as Problem;
  } catch (error) {
    console.error('Error fetching problem by ID:', error);
    return null;
  }
}
