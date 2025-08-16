'use client';

import { Problem } from '@/types';
import { useState } from 'react';
import { FaChevronDown, FaChevronUp, FaLink, FaExclamationTriangle } from 'react-icons/fa';
import { formatDistanceToNow } from 'date-fns';
import Link from 'next/link';

interface ProblemCardProps {
  problem: Problem;
}

export default function ProblemCard({ problem }: ProblemCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const toggleExpanded = () => {
    setIsExpanded(!isExpanded);
  };

  // Format the updated time as "X days/hours ago"
  const updatedTime = formatDistanceToNow(new Date(problem.updated_at), { addSuffix: true });

  return (
    <div className="border border-gray-200 rounded-lg shadow-sm bg-white overflow-hidden mb-6">
      <div 
        className="px-4 py-5 sm:px-6 cursor-pointer flex justify-between items-start"
        onClick={toggleExpanded}
      >
        <div>
          <h3 className="text-lg font-medium text-gray-900">{problem.statement}</h3>
          <p className="mt-1 max-w-2xl text-sm text-gray-500">
            Updated {updatedTime}
          </p>
        </div>
        <button 
          className="text-gray-400 hover:text-gray-600 p-2"
          aria-expanded={isExpanded}
          aria-label={isExpanded ? 'Collapse details' : 'Expand details'}
        >
          {isExpanded ? (
            <FaChevronUp className="h-5 w-5" />
          ) : (
            <FaChevronDown className="h-5 w-5" />
          )}
        </button>
      </div>

      {isExpanded && (
        <div className="border-t border-gray-200 px-4 py-5 sm:px-6">
          {problem.solution && (
            <div className="mb-4">
              <h4 className="text-md font-medium text-gray-900 mb-2">Solution</h4>
              <div className="bg-green-50 p-3 rounded-md">
                <p className="text-green-800">
                  {problem.solution}
                </p>
                {problem.has_negative_reviews && (
                  <div className="mt-2 flex items-center text-amber-600">
                    <FaExclamationTriangle className="h-4 w-4 mr-1" />
                    <span className="text-sm">
                      This solution has negative reviews.
                      {problem.review_url && (
                        <a 
                          href={problem.review_url} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="ml-1 underline"
                          onClick={(e) => e.stopPropagation()}
                        >
                          Read more
                        </a>
                      )}
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}

          <h4 className="text-md font-medium text-gray-900 mb-2">Sources</h4>
          <ul className="divide-y divide-gray-200">
            {problem.sources.map((source) => (
              <li key={source.id} className="py-3">
                <a 
                  href={source.url} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="flex items-start hover:bg-gray-50 rounded p-2"
                  onClick={(e) => e.stopPropagation()}
                >
                  <FaLink className="h-5 w-5 text-gray-400 mr-3 mt-0.5" />
                  <div>
                    <p className="font-medium text-blue-600">{source.title || source.url}</p>
                    {source.snippet && (
                      <p className="mt-1 text-sm text-gray-600">{source.snippet}</p>
                    )}
                  </div>
                </a>
              </li>
            ))}
          </ul>
          
          <div className="mt-4 pt-3 border-t border-gray-200">
            <Link
              href={`/problem/${problem.id}`}
              className="text-indigo-600 hover:text-indigo-900 font-medium"
              onClick={(e) => e.stopPropagation()}
            >
              View detailed problem page →
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
