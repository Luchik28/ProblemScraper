import { useEffect, useState } from 'react';
import { Problem } from '@/types';
import { mockProblems } from '../data/mock-data';
import Head from 'next/head';
import ProblemList from '@/components/ProblemList';

export default function Home() {
  const [problems, setProblems] = useState<Problem[]>([]);

  useEffect(() => {
    setProblems(mockProblems);
  }, []);
  
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
            
            <div className="bg-white shadow overflow-hidden sm:rounded-md">
              <ProblemList problems={problems} />
            </div>
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
