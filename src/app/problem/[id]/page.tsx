import Layout from '@/components/Layout';
import { getProblemById } from '@/lib/data';
import { formatDistanceToNow } from 'date-fns';
import Link from 'next/link';
import { notFound } from 'next/navigation';

export const revalidate = 3600; // Revalidate this page every hour

interface ProblemPageProps {
  params: {
    id: string;
  };
}

export default async function ProblemPage({ params }: ProblemPageProps) {
  const problem = await getProblemById(params.id);
  
  if (!problem) {
    notFound();
  }

  return (
    <Layout>
      <div className="mb-6">
        <Link 
          href="/"
          className="text-indigo-600 hover:text-indigo-900"
        >
          ← Back to all problems
        </Link>
      </div>
      
      <div className="bg-white shadow overflow-hidden sm:rounded-lg">
        <div className="px-4 py-5 sm:px-6">
          <h1 className="text-2xl font-bold text-gray-900">{problem.statement}</h1>
          <p className="mt-1 max-w-2xl text-sm text-gray-500">
            Added {formatDistanceToNow(new Date(problem.created_at), { addSuffix: true })}
          </p>
        </div>
        <div className="border-t border-gray-200 px-4 py-5 sm:px-6">
          <dl className="grid grid-cols-1 gap-x-4 gap-y-8 sm:grid-cols-2">
            {problem.solution && (
              <div className="sm:col-span-2">
                <dt className="text-sm font-medium text-gray-500">Potential Solution</dt>
                <dd className="mt-1 text-sm text-gray-900">{problem.solution}</dd>
              </div>
            )}
            
            <div className="sm:col-span-1">
              <dt className="text-sm font-medium text-gray-500">Status</dt>
              <dd className="mt-1 text-sm text-gray-900">
                <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">
                  Active
                </span>
              </dd>
            </div>
            
            {problem.has_negative_reviews && problem.review_url && (
              <div className="sm:col-span-1">
                <dt className="text-sm font-medium text-gray-500">Reviews</dt>
                <dd className="mt-1 text-sm text-gray-900">
                  <a 
                    href={problem.review_url} 
                    target="_blank" 
                    rel="noopener noreferrer" 
                    className="text-indigo-600 hover:text-indigo-900"
                  >
                    View negative reviews
                  </a>
                </dd>
              </div>
            )}
            
            <div className="sm:col-span-2">
              <dt className="text-sm font-medium text-gray-500">Sources</dt>
              <dd className="mt-1 text-sm text-gray-900">
                <ul className="border border-gray-200 rounded-md divide-y divide-gray-200">
                  {problem.sources.map((source) => (
                    <li key={source.id} className="pl-3 pr-4 py-3 flex items-center justify-between text-sm">
                      <div className="w-0 flex-1 flex items-center">
                        <span className="ml-2 flex-1 w-0 truncate">
                          {source.title || source.url}
                          {source.snippet && (
                            <p className="text-xs text-gray-500 mt-1">{source.snippet}</p>
                          )}
                        </span>
                      </div>
                      <div className="ml-4 flex-shrink-0">
                        <a href={source.url} target="_blank" rel="noopener noreferrer" className="font-medium text-indigo-600 hover:text-indigo-500">
                          Visit
                        </a>
                      </div>
                    </li>
                  ))}
                </ul>
              </dd>
            </div>
          </dl>
        </div>
      </div>
    </Layout>
  );
}
