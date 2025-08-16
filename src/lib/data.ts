import { Problem } from '@/types';
import mockProblemsData from '../data/mock-problems.json';

// Create a properly typed mock data object
const mockProblems = mockProblemsData.map(problem => ({
  id: problem.id.toString(),
  statement: problem.statement,
  solution: problem.solution_info || '',
  has_negative_reviews: problem.has_negative_reviews,
  review_url: '',
  created_at: problem.created_at,
  updated_at: problem.created_at,
  sources: problem.sources.map(source => ({
    id: `src-${Math.floor(Math.random() * 10000)}`, // Deterministic ID for SSR
    title: source.title,
    url: source.url,
    snippet: ''
  }))
}));

export async function getProblems(): Promise<Problem[]> {
  try {
    // Use static mock data for build time
    return [...mockProblems];
  } catch (error) {
    console.error('Error fetching problems:', error);
    return [];
  }
}

export async function getProblemById(id: string): Promise<Problem | null> {
  try {
    // Get all problems and find the one by ID
    const problems = await getProblems();
    const problem = problems.find(p => p.id === id);
    
    if (!problem) return null;
    
    return problem;
  } catch (error) {
    console.error('Error fetching problem by ID:', error);
    return null;
  }
}
