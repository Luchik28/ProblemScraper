import { useRouter } from 'next/router';
import { useEffect, useState } from 'react';
import { Problem } from '@/types';
import { getProblems } from '@/utils/supabase';
import Head from 'next/head';
import Link from 'next/link';
import { FaArrowLeft, FaCheck, FaExclamationTriangle, FaLink } from 'react-icons/fa';

export default function ProblemDetail() {
  const router = useRouter();
  const { id } = router.query;
  const [problem, setProblem] = useState<Problem | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadProblem() {
      if (!id) return;
      
      try {
        setLoading(true);
        const problems = await getProblems();
        const foundProblem = problems.find(p => p.id === id);
        
        if (foundProblem) {
          setProblem(foundProblem);
        } else {
          setError('Problem not found');
        }
      } catch (error) {
        console.error('Error loading problem:', error);
        setError('Failed to load problem details');
      } finally {
        setLoading(false);
      }
    }

    loadProblem();
  }, [id]);

  // Format the updated time
  const formattedDate = problem ? new Date(problem.updated_at).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  }) : '';

  return (
    <div className="min-h-screen flex flex-col">
      <Head>
        <title>{problem ? `${problem.statement.substring(0, 50)}...` : 'Problem Details'} | Problem Finder</title>
        <meta 
          name="description" 
          content={problem ? problem.statement : 'Problem details page'} 
        />
      </Head>
      
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <h1 className="text-xl font-bold text-gray-900">Problem Finder</h1>
            <nav className="flex space-x-4">
              <Link href="/" className="text-gray-600 hover:text-gray-900">Home</Link>
              <Link href="/about" className="text-gray-600 hover:text-gray-900">About</Link>
            </nav>
          </div>
        </div>
      </header>
      
      <main className="flex-grow bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="mb-6">
            <Link 
              href="/"
              className="inline-flex items-center text-gray-700 hover:text-gray-900"
            >
              <FaArrowLeft className="mr-2 h-4 w-4" />
              Back to all problems
            </Link>
          </div>

          {loading ? (
            <div className="flex justify-center items-center py-12">
              <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
            </div>
          ) : error ? (
            <div className="bg-red-50 border border-red-200 text-red-800 rounded-lg p-4">
              <p>{error}</p>
              <p className="mt-2">
                <Link href="/" className="text-red-600 font-medium hover:text-red-800">
                  Return to homepage
                </Link>
              </p>
            </div>
          ) : problem ? (
            <div className="bg-white shadow overflow-hidden sm:rounded-lg">
              <div className="px-4 py-5 sm:px-6 border-b border-gray-200">
                <h2 className="text-2xl font-bold text-gray-900">{problem.statement}</h2>
                <p className="mt-2 text-sm text-gray-500">
                  Last updated on {formattedDate}
                </p>
                
                <div className="mt-3 flex flex-wrap gap-2">
                  {/* Solution tag - switched: no solution is green (opportunity), has solution is gray */}
                  <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                    !problem.solution ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                  }`}>
                    {!problem.solution ? (
                      <>
                        <FaCheck className="mr-1 h-3 w-3" />
                        No Solution Yet
                      </>
                    ) : 'Has Solution'}
                  </span>
                  
                  {/* Complaint count tag - We don't need dynamic color here since it's just one problem */}
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-200 text-blue-800">
                    {problem.sources.length} {problem.sources.length === 1 ? 'Complaint' : 'Complaints'}
                  </span>
                  
                  {/* Warning tag if it has negative reviews */}
                  {problem.has_negative_reviews && (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                      <FaExclamationTriangle className="mr-1 h-3 w-3" />
                      Negative Reviews
                    </span>
                  )}
                </div>
              </div>
              
              {problem.solution && (
                <div className="px-4 py-5 sm:px-6 border-b border-gray-200">
                  <h3 className="text-lg font-medium text-gray-900 mb-3">Solution</h3>
                  <div className="bg-green-50 p-4 rounded-md">
                    <p className="text-green-800">
                      {problem.solution}
                    </p>
                    {problem.solution_url && problem.solution_url.startsWith('http') && (
                      <div className="mt-3">
                        <a 
                          href={problem.solution_url} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="inline-flex items-center text-green-700 hover:text-green-900"
                        >
                          <FaLink className="mr-2 h-4 w-4" />
                          View Solution
                        </a>
                      </div>
                    )}
                    {problem.has_negative_reviews && problem.review_url && (
                      <div className="mt-3 flex items-center text-amber-600">
                        <FaExclamationTriangle className="h-4 w-4 mr-2" />
                        <span>
                          This solution has received negative reviews.
                          <a 
                            href={problem.review_url} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="ml-1 underline"
                          >
                            Read more about the issues
                          </a>
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              )}
              
              <div className="px-4 py-5 sm:px-6">
                <h3 className="text-lg font-medium text-gray-900 mb-3">Sources</h3>
                {problem.sources.length > 0 ? (
                  <ul className="divide-y divide-gray-200 border border-gray-200 rounded-md">
                    {problem.sources.map((source) => (
                      <li key={source.id} className="p-4 hover:bg-gray-50">
                        <a 
                          href={source.url} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="flex items-start"
                        >
                          <FaLink className="h-5 w-5 text-gray-400 mr-3 mt-0.5" />
                          <div>
                            <p className="font-medium text-gray-700">{source.title}</p>
                            <p className="text-xs text-gray-500 mt-1">
                              {source.url}
                            </p>
                          </div>
                        </a>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-gray-500">No sources available for this problem.</p>
                )}
              </div>
            </div>
          ) : null}
        </div>
      </main>
      
      <footer className="bg-white border-t border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <p className="text-center text-gray-500 text-sm">
            &copy; {new Date().getFullYear()} Problem Finder. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  );
}
