export type UserRole = 'ADMIN' | 'EDITOR' | 'TEAM_REPORTER';
export const USER_ROLES: { value: UserRole; label: string }[] = [
  { value: 'ADMIN', label: 'Administrator' },
  { value: 'EDITOR', label: 'Redaktion' },
  { value: 'TEAM_REPORTER', label: 'Mannschaftsberichte' },
];

export interface MemberData {
  first_name: string;
  last_name: string;
  birth_date: string | null;
  joined_at: string | null;
  eligible_since: string | null;
  ttc_eligible_since: string | null;
  is_active: boolean;
  membership_end_date: string | null;
  phone: string | null;
  mobile: string | null;
  email: string | null;
  street: string | null;
  house_number: string | null;
  postal_code: string | null;
  city: string | null;
}
export interface Member extends MemberData {
  id: number;
}
export interface MemberOption {
  id: number;
  first_name: string;
  last_name: string;
  user_id: number | null;
}
export interface UserWrite {
  name: string;
  email: string;
  roles: UserRole[];
  is_active: boolean;
  member_id: number | null;
  member: MemberData | null;
}
export interface ManagedUser extends UserWrite {
  id: number;
  created_at: string;
  member: Member | null;
}
export interface UserPage {
  items: ManagedUser[];
  total: number;
}
