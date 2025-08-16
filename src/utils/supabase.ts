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
    
    // Otherwise, fetch from Supabase
    const { data, error } = await supabase
      .from('problems')
      .select(`
        id, 
        statement, 
        solution, 
        has_negative_reviews, 
        review_url, 
        created_at, 
        updated_at,
        sources (
          id, 
          title, 
          url, 
          snippet
        )
      `)
      .order('updated_at', { ascending: false });
    
    if (error) {
      console.error('Error fetching from Supabase:', error);
      return mockProblems;
    }
    
    if (!data || data.length === 0) {
      console.warn('No data found in Supabase, using mock data');
      return mockProblems;
    }
    
    return data as Problem[];
  } catch (error) {
    console.error('Error in getProblems:', error);
    return mockProblems;
  }
}
