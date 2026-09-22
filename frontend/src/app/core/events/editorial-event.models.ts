export interface EditorialEventInput {
  title: string;
  starts_at: string;
  ends_at: string | null;
  category_id: number;
  location: string | null;
  description: string | null;
}
