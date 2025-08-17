export interface Source {
  id: string;
  title: string;
  url: string;
  snippet: string;
}

export interface Problem {
  id: string;
  statement: string;
  solution: string;
  solution_url?: string;
  has_negative_reviews: boolean;
  review_url: string;
  created_at: string;
  updated_at: string;
  sources: Source[];
}
