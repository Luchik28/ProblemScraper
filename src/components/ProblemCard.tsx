'use client';

import { Problem } from '@/types';
import { useState } from 'react';
import Link from 'next/link';
import { FaCheck, FaExclamationTriangle, FaEye, FaLink } from 'react-icons/fa';

interface ProblemCardProps {
  problem: Problem;
}

// Function to calculate the color class based on complaint count
// We'll need the max complaints to make this relative
const getComplaintColorClass = (count: number) => {
  // Define color classes from lightest to darkest blue
  const colorClasses = [
    'bg-blue-50 text-blue-600',   // Very light blue (1-2 complaints)
    'bg-blue-100 text-blue-700',  // Light blue (3-5 complaints)
    'bg-blue-200 text-blue-800',  // Medium light blue (6-10 complaints)
    'bg-blue-300 text-blue-800',  // Medium blue (11-15 complaints)
    'bg-blue-400 text-blue-900',  // Medium dark blue (16-20 complaints)
    'bg-blue-500 text-white',     // Dark blue (21-30 complaints)
    'bg-blue-600 text-white',     // Very dark blue (30+ complaints)
  ];
  
  // Map the count to an index in the colorClasses array
  if (count <= 2) return colorClasses[0];
  if (count <= 5) return colorClasses[1];
  if (count <= 10) return colorClasses[2];
  if (count <= 15) return colorClasses[3];
  if (count <= 20) return colorClasses[4];
  if (count <= 30) return colorClasses[5];
  return colorClasses[6]; // 30+ complaints
}

export default function ProblemCard({ problem }: ProblemCardProps) {
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
    <Link 
      href={`/problem/${problem.id}`}
      className="flex flex-col h-full border border-gray-200 rounded-lg shadow-sm bg-white overflow-hidden hover:shadow-md transition-shadow duration-200 cursor-pointer no-underline"
    >
      <div className="p-5 flex-grow">
        <h3 className="text-lg font-medium text-gray-900 mb-2 line-clamp-2">{problem.statement}</h3>
        
        <div className="flex flex-wrap gap-2 mb-3">
          {/* Solution tag - switched: no solution is green (opportunity), has solution is gray */}
          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
            !problem.solution ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
          }`}
          onClick={(e) => e.stopPropagation()}>
            {!problem.solution ? (
              <>
                <FaCheck className="mr-1 h-3 w-3" />
                No Solution Yet
              </>
            ) : 'Has Solution'}
          </span>
          
          {/* Complaint count tag - dynamic blue scale based on count */}
          <span 
            className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getComplaintColorClass(problem.sources.length)}`}
            onClick={(e) => e.stopPropagation()}
          >
            {complaintCount} {complaintCount === 1 ? 'Complaint' : 'Complaints'}
          </span>
          
          {/* Warning tag if it has negative reviews */}
          {problem.has_negative_reviews && (
            <span 
              className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800"
              onClick={(e) => e.stopPropagation()}
            >
              <FaExclamationTriangle className="mr-1 h-3 w-3" />
              Negative Reviews
            </span>
          )}
        </div>
        
        <p className="text-sm text-gray-500">
          Updated: {formattedDate}
        </p>
      </div>
    </Link>
  );
}
