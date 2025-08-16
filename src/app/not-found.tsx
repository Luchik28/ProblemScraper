import Layout from '@/components/Layout';
import Link from 'next/link';

export default function NotFound() {
  return (
    <Layout>
      <div className="min-h-[60vh] flex flex-col items-center justify-center text-center px-4 sm:px-6 lg:px-8">
        <h2 className="text-3xl font-bold text-gray-900 mb-4">404 - Page Not Found</h2>
        <p className="text-xl text-gray-600 mb-8">The page you are looking for doesn't exist or has been moved.</p>
        <Link 
          href="/"
          className="inline-flex items-center px-4 py-2 border border-transparent text-base font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
        >
          Return Home
        </Link>
      </div>
    </Layout>
  );
}
