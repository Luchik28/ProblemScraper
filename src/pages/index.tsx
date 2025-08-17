import { useEffect, useState } from 'react';
import { Problem } from '@/types';
import Head from 'next/head';
import { getProblems } from '@/utils/supabase';
import Link from 'next/link';
import { FaSort, FaSortUp, FaSortDown } from 'react-icons/fa';
import ProblemCardGrid from '@/components/ProblemCardGrid';

type SortOption = 'sources' | 'updated' | 'none';
type SortDirection = 'asc' | 'desc';

export default function Home() {
  const [problems, setProblems] = useState<Problem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [sortOption, setSortOption] = useState<SortOption>('sources');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

  useEffect(() => {
    async function loadProblems() {
      try {
        setLoading(true);
        const problemsData = await getProblems();
        setProblems(problemsData);
      } catch (error) {
        console.error('Error loading problems:', error);
      } finally {
        setLoading(false);
      }
    }

    loadProblems();
  }, []);

  const toggleSort = (option: SortOption) => {
    if (sortOption === option) {
      // Toggle direction if same option is clicked
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      // Set new sort option with default desc direction
      setSortOption(option);
      setSortDirection('desc');
    }
  };

  const getSortIcon = (option: SortOption) => {
    if (sortOption !== option) return <FaSort className="ml-1 h-4 w-4" />;
    return sortDirection === 'asc' 
      ? <FaSortUp className="ml-1 h-4 w-4 text-blue-600" /> 
      : <FaSortDown className="ml-1 h-4 w-4 text-blue-600" />;
  };

  // Sort problems based on current sort option and direction
  const sortedProblems = [...problems].sort((a, b) => {
    // First, sort unsolved problems to the top
    if (!a.solution && b.solution) {
      return -1; // a comes first (unsolved)
    }
    if (a.solution && !b.solution) {
      return 1; // b comes first (unsolved)
    }
    
    // Then apply the selected sort option
    if (sortOption === 'sources') {
      const diff = a.sources.length - b.sources.length;
      return sortDirection === 'asc' ? diff : -diff;
    } else if (sortOption === 'updated') {
      const dateA = new Date(a.updated_at).getTime();
      const dateB = new Date(b.updated_at).getTime();
      return sortDirection === 'asc' ? dateA - dateB : dateB - dateA;
    }
    return 0;
  });
  
  return (
    <div className="min-h-screen flex flex-col">
      <Head>
        <title>Problem Finder - Discover Product Opportunities</title>
        <meta 
          name="description" 
          content="Explore real problems that need solutions. Each problem represents a potential product opportunity." 
        />
      </Head>
      
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <h1 className="text-xl font-bold text-gray-900">Problem Finder</h1>
            <nav className="flex space-x-4">
              <a href="/" className="text-gray-600 hover:text-gray-900">Home</a>
              <a href="/about" className="text-gray-600 hover:text-gray-900">About</a>
            </nav>
          </div>
        </div>
      </header>
      
      <main className="flex-grow bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="space-y-6">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Product Problems</h1>
              <p className="mt-2 text-gray-600">
                Discover real problems that need solutions. Each problem represents a potential product opportunity.
              </p>
            </div>
            
            {loading ? (
              <div className="flex justify-center items-center py-12">
                <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
              </div>
            ) : (
              <div>
                <div className="mb-4 flex justify-end">
                  <div className="inline-flex rounded-md shadow-sm">
                    <button
                      type="button"
                      className={`relative inline-flex items-center px-3 py-2 text-sm font-medium rounded-l-md border ${
                        sortOption === 'sources' ? 'bg-blue-50 text-blue-700 border-blue-300' : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                      }`}
                      onClick={() => toggleSort('sources')}
                    >
                      Sort by Complaints {getSortIcon('sources')}
                    </button>
                    <button
                      type="button"
                      className={`relative inline-flex items-center px-3 py-2 text-sm font-medium rounded-r-md border ${
                        sortOption === 'updated' ? 'bg-blue-50 text-blue-700 border-blue-300' : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                      }`}
                      onClick={() => toggleSort('updated')}
                    >
                      Sort by Updated {getSortIcon('updated')}
                    </button>
                  </div>
                </div>

                {problems.length > 0 ? (
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
                    {sortedProblems.map((problem) => (
                      <ProblemCardGrid key={problem.id} problem={problem} />
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-12 bg-white rounded-lg shadow">
                    <h3 className="text-lg font-medium text-gray-900 mb-2">No problems found</h3>
                    <p className="text-gray-500">
                      Check back later as our system continuously finds new product problems.
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>
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
