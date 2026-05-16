import { createClient, Session, SupabaseClient } from '@supabase/supabase-js';
import { AccountProfile } from './api';

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || '';
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '';

let client: SupabaseClient | null = null;

export function authConfigured() {
  return Boolean(SUPABASE_URL && SUPABASE_ANON_KEY);
}

export function getSupabaseClient() {
  if (!authConfigured()) return null;
  if (!client) client = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
  return client;
}

export function profileFromSession(session: Session | null, fallback: AccountProfile): AccountProfile {
  const user = session?.user;
  if (!user) return fallback;
  return {
    owner_id: user.id,
    label: user.email || user.user_metadata?.full_name || 'Signed-in user',
    plan: 'Free',
  };
}

export async function getCurrentSession() {
  const supabase = getSupabaseClient();
  if (!supabase) return null;
  const { data, error } = await supabase.auth.getSession();
  if (error) throw error;
  return data.session;
}

export function onAuthStateChange(callback: (session: Session | null) => void) {
  const supabase = getSupabaseClient();
  if (!supabase) return () => undefined;
  const { data } = supabase.auth.onAuthStateChange((_event, session) => callback(session));
  return () => data.subscription.unsubscribe();
}

export async function signInWithGoogle() {
  const supabase = getSupabaseClient();
  if (!supabase) throw new Error('Supabase Auth is not configured.');
  const { error } = await supabase.auth.signInWithOAuth({
    provider: 'google',
    options: { redirectTo: window.location.origin },
  });
  if (error) throw error;
}

export async function signInWithEmail(email: string) {
  const supabase = getSupabaseClient();
  if (!supabase) throw new Error('Supabase Auth is not configured.');
  const { error } = await supabase.auth.signInWithOtp({
    email,
    options: { emailRedirectTo: window.location.origin },
  });
  if (error) throw error;
}

export async function signOut() {
  const supabase = getSupabaseClient();
  if (!supabase) return;
  const { error } = await supabase.auth.signOut();
  if (error) throw error;
}
