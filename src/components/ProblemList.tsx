'use client';

import { Problem } from '@/types';
import ProblemCard from './ProblemCard';

interface ProblemListProps {
  problems: Problem[];
}

export default function ProblemList({ problems }: ProblemListProps) {
  if (problems.length === 0) {
    return (
      <div className="text-center py-12">
        <h3 className="text-lg font-medium text-gray-900 mb-2">No problems found</h3>
        <p className="text-gray-500">
          Check back later as our system continuously finds new product problems.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {problems.map((problem) => (
        <ProblemCard key={problem.id} problem={problem} />
      ))}
    </div>
  );
}
