import Layout from '@/components/Layout';
import Link from 'next/link';

export const metadata = {
  title: 'About Problem Finder',
  description: 'Learn more about Problem Finder and how it works',
};

export default function AboutPage() {
  return (
    <Layout>
      <div className="space-y-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">About Problem Finder</h1>
          <p className="mt-2 text-gray-600">
            Discover how Problem Finder helps entrepreneurs identify product opportunities.
          </p>
        </div>
        
        <div className="bg-white shadow overflow-hidden sm:rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">What is Problem Finder?</h2>
            <p className="text-gray-600 mb-4">
              Problem Finder is an automated tool that continuously scans the web for problems people are experiencing. 
              It uses natural language processing to identify real problems that could be solved with a product or service.
            </p>
            <p className="text-gray-600 mb-4">
              Our goal is to help entrepreneurs and product builders identify opportunities by showing them real problems
              that need solutions. Each problem we list represents a potential business opportunity.
            </p>
            <p className="text-gray-600">
              The system automatically updates several times a day, finding new problems and checking if existing problems
              have been solved.
            </p>
          </div>
        </div>
        
        <div className="bg-white shadow overflow-hidden sm:rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">How it Works</h2>
            <ol className="list-decimal pl-5 space-y-3 text-gray-600">
              <li>
                <strong>Problem Discovery:</strong> Our automated system scans forums, review sites, social media, and other
                platforms to identify problems people are experiencing.
              </li>
              <li>
                <strong>Semantic Analysis:</strong> We use AI to understand the context and identify if a statement is truly 
                a problem that could be solved with a product.
              </li>
              <li>
                <strong>Solution Potential:</strong> Problems are evaluated for their potential to be solved by a product or service.
              </li>
              <li>
                <strong>Continuous Updates:</strong> The system regularly checks if problems are still relevant and if solutions 
                exist.
              </li>
            </ol>
          </div>
        </div>
        
        <div className="bg-white shadow overflow-hidden sm:rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Start Exploring</h2>
            <p className="text-gray-600 mb-4">
              Ready to discover product opportunities? Head back to the main page to browse problems.
            </p>
            <Link 
              href="/" 
              className="inline-flex items-center px-4 py-2 border border-transparent text-base font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
            >
              Browse Problems
            </Link>
          </div>
        </div>
      </div>
    </Layout>
  );
}
