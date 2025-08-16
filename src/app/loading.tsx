import Layout from '@/components/Layout';

export default function Loading() {
  return (
    <Layout>
      <div className="space-y-6">
        <div>
          <div className="h-8 w-64 bg-gray-200 rounded animate-pulse"></div>
          <div className="mt-2 h-4 w-full max-w-2xl bg-gray-200 rounded animate-pulse"></div>
        </div>
        
        <div className="bg-white shadow overflow-hidden sm:rounded-md">
          <ul className="divide-y divide-gray-200">
            {[...Array(5)].map((_, i) => (
              <li key={i} className="px-4 py-4 sm:px-6">
                <div className="space-y-3">
                  <div className="h-5 bg-gray-200 rounded w-1/4 animate-pulse"></div>
                  <div className="h-4 bg-gray-200 rounded w-3/4 animate-pulse"></div>
                  <div className="h-4 bg-gray-200 rounded w-1/2 animate-pulse"></div>
                  <div className="flex space-x-2">
                    <div className="h-3 bg-gray-200 rounded w-12 animate-pulse"></div>
                    <div className="h-3 bg-gray-200 rounded w-12 animate-pulse"></div>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </Layout>
  );
}
