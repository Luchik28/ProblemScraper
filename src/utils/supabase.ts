import { createClient } from '@supabase/supabase-js';

// Types for our problems
export type Source = {
  title: string;
  url: string;
}

export type Problem = {
  id: number;
  statement: string;
  sources: Source[];
  has_solution: boolean;
  solution_info: string;
  has_negative_reviews: boolean;
  created_at: string;
}

// Function to create a Supabase client
export const createSupabaseClient = () => {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;
  
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
      // Use dynamic import for mock data
      const mockProblems = await import('../data/mock-problems.json');
      return mockProblems.default as Problem[];
    }
    
    // Otherwise, fetch from Supabase
    const { data, error } = await supabase
      .from('problems')
      .select('*')
      .order('id', { ascending: true });
    
    if (error) {
      console.error('Error fetching problems:', error);
      return [];
    }
    
    return data as Problem[] || [];
  } catch (err) {
    console.error('Failed to fetch problems:', err);
    return [];
  }
}
