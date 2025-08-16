import Layout from '@/components/Layout';
import ProblemList from '@/components/ProblemList';
import { getProblems } from '@/lib/data';

export const revalidate = 3600; // Revalidate this page every hour

export default async function Home() {
  const problems = await getProblems();
  
  return (
    <Layout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Product Problems</h1>
          <p className="mt-2 text-gray-600">
            Discover real problems that need solutions. Each problem represents a potential product opportunity.
          </p>
        </div>
        
        <div className="bg-white shadow overflow-hidden sm:rounded-md">
          <ProblemList problems={problems} />
        </div>
      </div>
    </Layout>
  );
}
