import { useEffect, useState } from 'react';
import Head from 'next/head';

export default function About() {
  return (
    <div className="min-h-screen flex flex-col">
      <Head>
        <title>About - Problem Finder</title>
        <meta 
          name="description" 
          content="Learn about the Problem Finder project and how it helps discover product opportunities." 
        />
      </Head>
      
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <h1 className="text-xl font-bold text-gray-900">Problem Finder</h1>
            <nav className="flex space-x-4">
              <a href="/" className="text-gray-600 hover:text-gray-900">Home</a>
              <a href="/about" className="text-gray-600 hover:text-gray-900">About</a>
            </nav>
          </div>
        </div>
      </header>
      
      <main className="flex-grow bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="prose prose-lg mx-auto">
            <h1 className="text-3xl font-bold text-gray-900">About Problem Finder</h1>
            
            <p className="text-gray-600">
              Problem Finder is a tool designed to help entrepreneurs, product managers, and innovators discover real problems
              that need solutions. We believe that successful products start with addressing genuine pain points.
            </p>
            
            <h2 className="text-2xl font-semibold text-gray-900 mt-8">How It Works</h2>
            
            <p className="text-gray-600">
              Our system scans various online sources, including forums, review sites, and discussion boards, to identify
              complaints and problems that people are experiencing. We then use natural language processing to cluster similar
              problems together, allowing you to see patterns and opportunities.
            </p>
            
            <h2 className="text-2xl font-semibold text-gray-900 mt-8">Use Cases</h2>
            
            <ul className="text-gray-600 list-disc pl-5 space-y-2">
              <li>Entrepreneurs looking for new business ideas</li>
              <li>Product managers seeking to improve existing products</li>
              <li>Researchers identifying market gaps</li>
              <li>Innovators wanting to solve real problems</li>
            </ul>
          </div>
        </div>
      </main>
      
      <footer className="bg-white border-t border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <p className="text-center text-gray-500 text-sm">
            &copy; {new Date().getFullYear()} Problem Finder. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  );
}
