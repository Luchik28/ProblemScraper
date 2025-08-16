'use client';

import Layout from '@/components/Layout';
import Link from 'next/link';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <Layout>
      <div className="min-h-[60vh] flex flex-col items-center justify-center text-center px-4 sm:px-6 lg:px-8">
        <h2 className="text-3xl font-bold text-red-600 mb-4">Oops! Something went wrong</h2>
        <p className="text-xl text-gray-600 mb-8">{error.message || 'An unexpected error occurred.'}</p>
        <div className="flex flex-col sm:flex-row space-y-4 sm:space-y-0 sm:space-x-4">
          <button
            onClick={() => reset()}
            className="inline-flex items-center px-4 py-2 border border-transparent text-base font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
          >
            Try again
          </button>
          <Link 
            href="/"
            className="inline-flex items-center px-4 py-2 border border-gray-300 text-base font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
          >
            Return home
          </Link>
        </div>
      </div>
    </Layout>
  );
}
