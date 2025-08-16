<!-- Use this file to provide workspace-specific custom instructions to Copilot. For more details, visit https://code.visualstudio.com/docs/copilot/copilot-customization#_use-a-githubcopilotinstructionsmd-file -->

# Problem Finder Web Application

This is a Next.js application that displays product problems scraped by a Python script. The application uses:

- Next.js 14 with App Router
- TypeScript for type safety
- Tailwind CSS for styling
- Supabase for database functionality
- GitHub Actions for automated script runs

The application displays a list of problems that could be solved with software products, along with their sources and potential solutions.

## Key Concepts:

1. Problems are stored in a Supabase PostgreSQL database
2. The Python script runs periodically via GitHub Actions to update the database
3. The web application fetches and displays the problems from the database
4. Each problem includes a title, description, sources, and potential solutions

When suggesting code, focus on performance, maintainability, and user experience. Use modern React patterns with the App Router and Server Components where appropriate.
