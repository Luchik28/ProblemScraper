'use client';

import { Problem } from '@/types';
import ProblemCard from './ProblemCard';
import { useState } from 'react';
import { FaSort, FaSortUp, FaSortDown } from 'react-icons/fa';

interface ProblemGridProps {
  problems: Problem[];
}

type SortOption = 'sources' | 'updated' | 'none';
type SortDirection = 'asc' | 'desc';

export default function ProblemGrid({ problems }: ProblemGridProps) {
  const [sortOption, setSortOption] = useState<SortOption>('sources');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

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
            Sort by Sources {getSortIcon('sources')}
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

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
        {sortedProblems.map((problem) => (
          <ProblemCard key={problem.id} problem={problem} />
        ))}
      </div>
    </div>
  );
}
