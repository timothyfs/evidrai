'use client';

import { useEffect, useMemo, useState } from 'react';
import { EmailOtpType } from '@supabase/supabase-js';
import { getSupabaseClient } from '../../../lib/auth';

const ALLOWED_TYPES = new Set(['signup', 'invite', 'magiclink', 'recovery', 'email_change', 'email'] as const);

type AuthStatus = 'Verifying your link…' | 'Your link has been verified. Redirecting…' | 'Could not verify this link.';

function safeNextUrl(value: string | null) {
  if (!value) return '/';
  try {
    const parsed = new URL(value, window.location.origin);
    if (parsed.origin !== window.location.origin) return '/';
    return `${parsed.pathname}${parsed.search}${parsed.hash}` || '/';
  } catch {
    return '/';
  }
}

export default function AuthConfirmPage() {
  const [status, setStatus] = useState<AuthStatus>('Verifying your link…');
  const [detail, setDetail] = useState('Please wait while Evidrai confirms your account link.');
  const params = useMemo(() => {
    if (typeof window === 'undefined') return new URLSearchParams();
    return new URLSearchParams(window.location.search);
  }, []);

  useEffect(() => {
    async function confirmLink() {
      const supabase = getSupabaseClient();
      if (!supabase) {
        setStatus('Could not verify this link.');
        setDetail('Supabase Auth is not configured for this deployment.');
        return;
      }

      const tokenHash = params.get('token_hash') || '';
      const type = params.get('type') || 'invite';
      const next = safeNextUrl(params.get('next') || params.get('redirect_to'));

      if (!tokenHash || !ALLOWED_TYPES.has(type as never)) {
        setStatus('Could not verify this link.');
        setDetail('The invite link is missing required verification details. Ask the Evidrai admin to resend it.');
        return;
      }

      const { error } = await supabase.auth.verifyOtp({
        token_hash: tokenHash,
        type: type as EmailOtpType,
      });

      if (error) {
        setStatus('Could not verify this link.');
        setDetail(error.message || 'The link may have expired or already been used. Ask the Evidrai admin to resend it.');
        return;
      }

      setStatus('Your link has been verified. Redirecting…');
      setDetail('Taking you back to Evidrai.');
      window.location.assign(next);
    }

    confirmLink();
  }, [params]);

  return (
    <main className="authConfirmPage">
      <section className="card loginGate">
        <p className="eyebrow">Evidrai account</p>
        <h1>{status}</h1>
        <p className="muted">{detail}</p>
        {status === 'Could not verify this link.' && <p><a href="/">Return to Evidrai</a></p>}
      </section>
    </main>
  );
}
