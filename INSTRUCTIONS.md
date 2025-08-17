# Instructions for Running Problem Finder Scripts

## Testing the Setup

To verify your environment and Supabase connection:

```bash
cd /Users/Daniel/Documents/coding/Problem\ Scraper/problem-finder-web
python scripts/test_connection.py
```

## Running the Problem Finder

To run the main problem finder script that updates the database:

```bash
cd /Users/Daniel/Documents/coding/Problem\ Scraper/problem-finder-web
python scripts/problem_finder_update.py
```

## Running the Frontend

To run the Next.js frontend locally:

```bash
cd /Users/Daniel/Documents/coding/Problem\ Scraper/problem-finder-web
npm run dev
```

## Building for Production

To build the frontend for production:

```bash
cd /Users/Daniel/Documents/coding/Problem\ Scraper/problem-finder-web
npm run build
```
