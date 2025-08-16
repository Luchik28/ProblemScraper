'use client';

import { useEffect, useState } from 'react';
import Layout from '@/components/Layout';
import ProblemList from '@/components/ProblemList';
import { Problem } from '@/types';
import { mockProblems } from '../data/mock-data';

export default function Home() {
  const [problems, setProblems] = useState<Problem[]>([]);

  useEffect(() => {
    setProblems(mockProblems);
  }, []);
  
  return (
    <Layout>
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
    </Layout>
  );
}
