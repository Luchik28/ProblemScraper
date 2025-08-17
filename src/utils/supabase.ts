import { createClient } from '@supabase/supabase-js';
import { Problem } from '@/types';
import { mockProblems } from '@/data/mock-data';

// Function to create a Supabase client
export const createSupabaseClient = () => {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  
  if (!supabaseUrl || !supabaseAnonKey) {
    console.warn('Supabase credentials not found, using mock data');
    return null;
  }
  
  return createClient(supabaseUrl, supabaseAnonKey);
}

// Function to fetch problems
export async function getProblems(): Promise<Problem[]> {
  try {
    const supabase = createSupabaseClient();
    
    // If Supabase client couldn't be created, use mock data
    if (!supabase) {
      return mockProblems;
    }
    
    // First, fetch the problems
    const { data: problemsData, error: problemsError } = await supabase
      .from('problems')
      .select('*')
      .order('updated_at', { ascending: false });
    
    if (problemsError || !problemsData || problemsData.length === 0) {
      console.error('Error fetching problems from Supabase or no problems found:', problemsError);
      return mockProblems;
    }
    
    // Then, for each problem, fetch its sources using the junction table
    const problems = await Promise.all(problemsData.map(async (problem) => {
      const { data: sourceLinks, error: linksError } = await supabase
        .from('problem_sources')
        .select('source_id')
        .eq('problem_id', problem.id);
      
      if (linksError || !sourceLinks || sourceLinks.length === 0) {
        // If no sources found or error, return problem with empty sources array
        return { ...problem, sources: [] };
      }
      
      // Get all source IDs for this problem
      const sourceIds = sourceLinks.map(link => link.source_id);
      
      // Fetch the actual sources
      const { data: sources, error: sourcesError } = await supabase
        .from('sources')
        .select('*')
        .in('id', sourceIds);
      
      if (sourcesError || !sources) {
        // If error fetching sources, return problem with empty sources array
        return { ...problem, sources: [] };
      }
      
      // Return the problem with its sources
      return { ...problem, sources };
    }));
    
    console.log('Fetched problems from Supabase:', problems);
    return problems as Problem[];
  } catch (error) {
    console.error('Error in getProblems:', error);
    return mockProblems;
  }
}
