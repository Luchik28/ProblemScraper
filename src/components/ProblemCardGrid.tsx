'use client';

import { Problem } from '@/types';
import Link from 'next/link';
import { FaCheck, FaExclamationTriangle, FaEye, FaLink } from 'react-icons/fa';

interface ProblemCardGridProps {
  problem: Problem;
}

export default function ProblemCardGrid({ problem }: ProblemCardGridProps) {
  // Format the updated time
  const updatedDate = new Date(problem.updated_at);
  const formattedDate = updatedDate.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  });
  
  // Count of sources (complaints)
  const complaintCount = problem.sources.length;
  
  return (
    <div className="flex flex-col h-full border border-gray-200 rounded-lg shadow-sm bg-white overflow-hidden hover:shadow-md transition-shadow duration-200">
      <div className="p-5 flex-grow">
        <h3 className="text-lg font-medium text-gray-900 mb-2 line-clamp-2">{problem.statement}</h3>
        
        <div className="flex flex-wrap gap-2 mb-3">
          {/* Has solution tag */}
          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
            problem.solution ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
          }`}>
            {problem.solution ? (
              <>
                <FaCheck className="mr-1 h-3 w-3" />
                Has Solution
              </>
            ) : 'No Solution Yet'}
          </span>
          
          {/* Complaint count tag */}
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
            {complaintCount} {complaintCount === 1 ? 'Complaint' : 'Complaints'}
          </span>
          
          {/* Warning tag if it has negative reviews */}
          {problem.has_negative_reviews && (
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
              <FaExclamationTriangle className="mr-1 h-3 w-3" />
              Negative Reviews
            </span>
          )}
        </div>
        
        <p className="text-sm text-gray-500 mb-3">
          Updated: {formattedDate}
        </p>
      </div>
      
      <div className="px-5 py-3 bg-gray-50 border-t border-gray-200">
        <Link 
          href={`/problem/${problem.id}`}
          className="inline-flex items-center justify-center w-full px-4 py-2 text-sm font-medium text-gray-700 bg-gray-200 rounded-md hover:bg-gray-300 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-400"
        >
          <FaEye className="mr-2 h-4 w-4" />
          View Details
        </Link>
      </div>
    </div>
  );
}
