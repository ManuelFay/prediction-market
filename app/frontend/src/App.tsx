import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient
} from '@tanstack/react-query';
import { api, API_BASE } from './api';
import {
  type CommentRead,
  type LedgerEntryRead,
  type MarketRead,
  type MarketWithBets,
  type PositionRead,
} from './types';
import { OddsChart } from './components/OddsChart';

const COMMENTS_PAGE_SIZE = 20;

type AdminSession = { authenticated: boolean; username: string; password: string };
type ActiveUser = { id: number; name: string } | null;

const STORAGE_KEYS = {
  activeUserId: 'activeUserId',
  activeUserName: 'activeUserName',
  userPasswords: 'userPasswords'
};

const loadStoredUser = (): ActiveUser => {
  const sessionId = Number(sessionStorage.getItem(STORAGE_KEYS.activeUserId) || '') || null;
  const sessionName = sessionStorage.getItem(STORAGE_KEYS.activeUserName) || '';
  if (sessionId) return { id: sessionId, name: sessionName };

  const legacyId = Number(localStorage.getItem(STORAGE_KEYS.activeUserId) || '') || null;
  const legacyName = localStorage.getItem(STORAGE_KEYS.activeUserName) || '';
  if (legacyId) {
    sessionStorage.setItem(STORAGE_KEYS.activeUserId, String(legacyId));
    sessionStorage.setItem(STORAGE_KEYS.activeUserName, legacyName);
    return { id: legacyId, name: legacyName };
  }

  return null;
};

const loadPasswords = (): Record<string, string> => {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEYS.userPasswords) || '{}');
  } catch (_err) {
    return {};
  }
};

const formatProb = (p: number) => `${(p * 100).toFixed(1)}%`;

function Chip({ label, ghost }: { label: string; ghost?: boolean }) {
  return (
    <span
      className={[
        'inline-flex items-center rounded-full border px-3 py-1 text-sm font-semibold',
        ghost
          ? 'border-slate-700 bg-slate-900 text-slate-200'
          : 'border-cyan-400 bg-gradient-to-r from-teal-400 to-blue-500 text-slate-900'
      ].join(' ')}
    >
      {label}
    </span>
  );
}

function Tag({ label, tone }: { label: string; tone?: 'success' | 'danger' }) {
  const toneClass =
    tone === 'success'
      ? 'bg-emerald-900/60 border-emerald-600'
      : tone === 'danger'
      ? 'bg-rose-900/60 border-rose-600'
      : 'bg-slate-800 border-slate-700';
  return (
    <span className={`inline-block rounded-full border px-2 py-0.5 text-xs ${toneClass}`}>
      {label}
    </span>
  );
}

function Button({
  children,
  variant = 'primary',
  disabled,
  onClick,
  type
}: {
  children: React.ReactNode;
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  disabled?: boolean;
  onClick?: React.MouseEventHandler<HTMLButtonElement>;
  type?: 'button' | 'submit';
}) {
  const base =
    'rounded-lg px-3 py-2 font-semibold transition hover:-translate-y-0.5 hover:shadow-lg text-left';
  const variants: Record<typeof variant, string> = {
    primary: 'bg-gradient-to-r from-teal-500 to-blue-500 text-slate-900 border border-blue-400',
    secondary: 'bg-slate-900 text-slate-100 border border-slate-700',
    danger: 'bg-rose-800 text-rose-50 border border-rose-500',
    ghost: 'bg-transparent text-slate-100 border border-slate-700'
  };
  return (
    <button
      type={type ?? 'button'}
      disabled={disabled}
      onClick={onClick}
      className={`${base} ${variants[variant]} ${
        disabled ? 'opacity-60 hover:translate-y-0 cursor-not-allowed' : ''
      }`}
    >
      {children}
    </button>
  );
}

function Modal({
  open,
  title,
  onClose,
  children
}: {
  open: boolean;
  title?: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  useEffect(() => {
    if (!open) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKeyDown);

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    return () => {
      window.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onMouseDown={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="max-h-[85vh] w-full max-w-4xl overflow-auto rounded-2xl border border-slate-800 bg-slate-950 shadow-2xl"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-slate-800 px-4 py-3">
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold text-slate-100">{title ?? 'Details'}</div>
            <div className="truncate text-xs text-slate-400">Click outside or press Esc to close</div>
          </div>
          <Button variant="secondary" onClick={onClose}>
            Close
          </Button>
        </div>
        <div className="p-4">{children}</div>
      </div>
    </div>
  );
}

function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div
      className={`rounded-xl border border-slate-800 bg-slate-900/90 p-4 shadow-deep ${className ?? ''}`}
    >
      {children}
    </div>
  );
}

function ListRow({ children }: { children: React.ReactNode }) {
  return <div className="border-b border-slate-800 px-2 py-2 last:border-b-0">{children}</div>;
}

function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={`w-full rounded-lg border border-slate-800 bg-slate-900 px-3 py-2 text-slate-100 ${
        props.className ?? ''
      }`}
    />
  );
}

function TextArea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      className={`w-full rounded-lg border border-slate-800 bg-slate-900 px-3 py-2 text-slate-100 ${
        props.className ?? ''
      }`}
    />
  );
}

export default function App() {
  const [activeTab, setActiveTab] = useState<'open' | 'positions' | 'ledger' | 'admin'>('open');
  const [activeUser, setActiveUser] = useState<ActiveUser>(loadStoredUser());
  const [passwords, setPasswords] = useState<Record<string, string>>(loadPasswords);
  const [adminSession, setAdminSession] = useState<AdminSession>({
    authenticated: false,
    username: '',
    password: ''
  });
  const [createOpen, setCreateOpen] = useState(false);
  const [selectedMarketId, setSelectedMarketId] = useState<number | null>(null);
  const [lastCreatedPassword, setLastCreatedPassword] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const isAdmin = adminSession.authenticated;
  const isLoggedIn = Boolean(activeUser);

  useEffect(() => {
    if (activeUser) {
      sessionStorage.setItem(STORAGE_KEYS.activeUserId, String(activeUser.id));
      sessionStorage.setItem(STORAGE_KEYS.activeUserName, activeUser.name);
    } else {
      sessionStorage.removeItem(STORAGE_KEYS.activeUserId);
      sessionStorage.removeItem(STORAGE_KEYS.activeUserName);
      localStorage.removeItem(STORAGE_KEYS.activeUserId);
      localStorage.removeItem(STORAGE_KEYS.activeUserName);
    }
  }, [activeUser]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.userPasswords, JSON.stringify(passwords));
  }, [passwords]);

  const usersQuery = useQuery({
    queryKey: ['users'],
    queryFn: api.listUsers
  });

  const marketsQuery = useQuery({
    queryKey: ['markets'],
    queryFn: api.listMarkets
  });

  const activeUserQuery = useQuery({
    queryKey: ['user', activeUser?.id],
    queryFn: () => api.getUser(activeUser!.id),
    enabled: Boolean(activeUser)
  });

  const ledgerQuery = useQuery({
    queryKey: ['ledger', activeUser?.id],
    queryFn: () => api.getLedger(activeUser!.id),
    enabled: Boolean(activeUser)
  });

  const positionsQuery = useQuery({
    queryKey: ['positions', activeUser?.id],
    queryFn: () => api.getPositions(activeUser!.id),
    enabled: Boolean(activeUser)
  });

  const adminDirectoryQuery = useQuery({
    queryKey: ['admin-users'],
    queryFn: () => api.listUsersWithPasswords({ username: adminSession.username, password: adminSession.password }),
    enabled: adminSession.authenticated
  });

  const marketDetailQuery = useQuery({
    queryKey: ['market', selectedMarketId],
    queryFn: () => api.getMarket(selectedMarketId!),
    enabled: Boolean(selectedMarketId)
  });

  const commentsQuery = useInfiniteQuery({
    queryKey: ['comments', selectedMarketId],
    queryFn: ({ pageParam = 1 }) => api.getComments(selectedMarketId!, pageParam, COMMENTS_PAGE_SIZE),
    getNextPageParam: (lastPage) => (lastPage.has_more ? lastPage.page + 1 : undefined),
    enabled: Boolean(selectedMarketId)
  });

  const setUserPassword = (id: number, password: string) => {
    if (!id || !password) return;
    setPasswords((prev) => ({ ...prev, [id]: password }));
  };

  const getUserPassword = (id?: number | null) => {
    if (!id) return '';
    return passwords[id] || '';
  };

  const clearSession = () => {
    setActiveUser(null);
    setSelectedMarketId(null);
    setCreateOpen(false);
  };

  const loginMutation = useMutation({
    mutationFn: async ({ username, password }: { username: string; password: string }) => {
      const isAdminUser = username.toLowerCase() === 'admin' && password === 'admin';
      if (isAdminUser) {
        setActiveUser(null);
        setAdminSession({ authenticated: true, username, password });
        return null;
      }
      const user = await api.login({ name: username, password });
      setAdminSession({ authenticated: false, username: '', password: '' });
      setUserPassword(user.id, password);
      setActiveUser({ id: user.id, name: user.name });
      return user;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['users'] });
      void queryClient.invalidateQueries({ queryKey: ['markets'] });
    },
    onError: (err: Error) => alert(err.message || 'Login failed')
  });

  const createUserMutation = useMutation({
    mutationFn: (name: string) => api.createUser(name, { username: adminSession.username, password: adminSession.password }),
    onSuccess: (user) => {
      setLastCreatedPassword(user.password);
      setUserPassword(user.id, user.password);
      void queryClient.invalidateQueries({ queryKey: ['users'] });
      void queryClient.invalidateQueries({ queryKey: ['admin-users'] });
    },
    onError: (err: Error) => alert(err.message || 'User creation failed')
  });

  const depositMutation = useMutation({
    mutationFn: ({ userId, amount }: { userId: number; amount: number }) =>
      api.deposit(userId, amount, { username: adminSession.username, password: adminSession.password }),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: ['users'] });
      void queryClient.invalidateQueries({ queryKey: ['user', variables.userId] });
    },
    onError: (err: Error) => alert(err.message || 'Top-up failed')
  });

  const deleteUserMutation = useMutation({
    mutationFn: (userId: number) =>
      api.deleteUser(userId, { username: adminSession.username, password: adminSession.password }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['users'] });
      void queryClient.invalidateQueries({ queryKey: ['admin-users'] });
      clearSession();
    },
    onError: (err: Error) => alert(err.message || 'Delete failed')
  });

  const resetMutation = useMutation({
    mutationFn: () => api.resetPlatform({ username: adminSession.username, password: adminSession.password }),
    onSuccess: () => {
      clearSession();
      void queryClient.invalidateQueries();
    },
    onError: (err: Error) => alert(err.message || 'Reset failed')
  });

  const createMarketMutation = useMutation({
    mutationFn: (payload: { question: string; description?: string; initial_prob_yes: number }) =>
      api.createMarket(activeUser!.id, payload),
    onSuccess: (market) => {
      setCreateOpen(false);
      void queryClient.invalidateQueries({ queryKey: ['markets'] });
      setSelectedMarketId(market.id);
      void queryClient.invalidateQueries({ queryKey: ['user', activeUser?.id] });
    },
    onError: (err: Error) => alert(err.message || 'Market creation failed')
  });

  const placeBetMutation = useMutation({
    mutationFn: ({ marketId, side }: { marketId: number; side: 'YES' | 'NO' }) =>
      api.placeBet(marketId, activeUser!.id, side, getUserPassword(activeUser?.id)),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: ['markets'] });
      void queryClient.invalidateQueries({ queryKey: ['market', variables.marketId] });
      void queryClient.invalidateQueries({ queryKey: ['user', activeUser?.id] });
      void queryClient.invalidateQueries({ queryKey: ['positions', activeUser?.id] });
    },
    onError: (err: Error) => alert(err.message || 'Bet failed')
  });

  const resolveMarketMutation = useMutation({
    mutationFn: ({ marketId, outcome }: { marketId: number; outcome: 'YES' | 'NO' | 'INVALID' }) =>
      api.resolveMarket(marketId, outcome),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: ['markets'] });
      void queryClient.invalidateQueries({ queryKey: ['market', variables.marketId] });
      void queryClient.invalidateQueries({ queryKey: ['positions', activeUser?.id] });
      void queryClient.invalidateQueries({ queryKey: ['user', activeUser?.id] });
    },
    onError: (err: Error) => alert(err.message || 'Resolution failed')
  });

  const deleteMarketMutation = useMutation({
    mutationFn: (marketId: number) => api.deleteMarket(marketId, activeUser!.id),
    onSuccess: () => {
      setSelectedMarketId(null);
      void queryClient.invalidateQueries({ queryKey: ['markets'] });
      void queryClient.invalidateQueries({ queryKey: ['user', activeUser?.id] });
    },
    onError: (err: Error) => alert(err.message || 'Delete failed')
  });

  const commentCreateMutation = useMutation({
    mutationFn: ({ marketId, text }: { marketId: number; text: string }) =>
      api.createComment(marketId, activeUser!.id, text, getUserPassword(activeUser?.id)),
    onSuccess: (_comment, variables) => {
      void queryClient.invalidateQueries({ queryKey: ['comments', variables.marketId] });
    },
    onError: (err: Error) => alert(err.message || 'Could not post comment')
  });

  const commentDeleteMutation = useMutation({
    mutationFn: ({ commentId, marketId }: { commentId: number; marketId: number }) =>
      api.deleteComment(commentId, activeUser!.id, getUserPassword(activeUser?.id)),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: ['comments', variables.marketId] });
    },
    onError: (err: Error) => alert(err.message || 'Could not delete comment')
  });

  const handleLogin = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const username = (form.get('username') as string)?.trim();
    const password = (form.get('password') as string)?.trim();
    if (!username || !password) {
      alert('Enter both username and password');
      return;
    }
    loginMutation.mutate({ username, password });
  };

  const handleLogout = () => {
    setAdminSession({ authenticated: false, username: '', password: '' });
    clearSession();
    queryClient.clear();
  };

  const markets = marketsQuery.data ?? [];
  const users = usersQuery.data ?? [];

  useEffect(() => {
    if (selectedMarketId && !markets.find((m) => m.id === selectedMarketId)) {
      setSelectedMarketId(null);
    }
  }, [markets, selectedMarketId]);

  const openMarkets = useMemo(() => markets.filter((m) => m.status === 'OPEN'), [markets]);
  const userPositions = positionsQuery.data ?? [];
  const userLedger = ledgerQuery.data ?? [];
  const selectedMarket = marketDetailQuery.data ?? null;

  const comments: CommentRead[] =
    commentsQuery.data?.pages.flatMap((p) => p.items) ?? [];

  const canActAsUser = isLoggedIn && !isAdmin;
  const activeUserPassword = getUserPassword(activeUser?.id);

  const authLabel = isAdmin
    ? 'Admin session'
    : isLoggedIn
    ? `Logged in as ${activeUser?.name}`
    : 'Offline';

  const marketStatusTone = (status: MarketRead['status']): 'success' | 'danger' | undefined => {
    if (status === 'RESOLVED') return 'success';
    if (status === 'INVALID') return 'danger';
    return undefined;
  };

  const renderLedger = (entries: LedgerEntryRead[]) => {
    if (!entries.length) return <div className="text-sm text-slate-400">No ledger entries yet.</div>;
    return (
      <div className="max-h-72 overflow-auto rounded-lg border border-slate-800">
        {entries.map((entry) => (
          <ListRow key={entry.id}>
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span>
                <Tag label={entry.entry_type} /> {entry.note ? `— ${entry.note}` : ''}
              </span>
              <span>{new Date(entry.created_at).toLocaleString()}</span>
            </div>
            <div className="text-sm font-semibold">{entry.amount.toFixed(2)} €</div>
          </ListRow>
        ))}
      </div>
    );
  };

  const renderPositions = (positions: PositionRead[]) => {
    if (!positions.length) return <div className="text-sm text-slate-400">No open positions.</div>;
    return (
      <div className="max-h-72 overflow-auto rounded-lg border border-slate-800">
        {positions.map((p) => (
          <ListRow key={`${p.market_id}-${p.side}`}>
            <div className="flex items-center justify-between">
              <strong>{p.market_question}</strong>
              <Tag label={p.market_status} tone={marketStatusTone(p.market_status as MarketRead['status'])} />
            </div>
            <div className="text-sm text-slate-300">Side: <Tag label={p.side} /></div>
            <div className="text-sm text-slate-200">
              Shares: {p.total_shares.toFixed(4)} | Stake: {p.total_stake.toFixed(2)}€ | Avg prob:{' '}
              {(p.avg_odds * 100).toFixed(2)}% | Potential payout: {p.potential_payout.toFixed(2)}€
            </div>
          </ListRow>
        ))}
      </div>
    );
  };

  const renderMarketList = (list: MarketRead[]) => {
    if (!list.length) return <div className="text-sm text-slate-400">No open markets yet.</div>;
    const authenticated = canActAsUser && Boolean(activeUserPassword);
    return (
      <div className="space-y-3">
        {list.map((m) => {
          const yesLocked = m.price_yes > 0.95;
          const noLocked = m.price_yes < 0.05;
          return (
            <div
              key={m.id}
              className="cursor-pointer rounded-xl border border-slate-800 bg-slate-900/90 p-3 shadow-inner hover:border-slate-700"
              role="button"
              tabIndex={0}
              onClick={() => setSelectedMarketId((prev) => (prev === m.id ? null : m.id))}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') setSelectedMarketId((prev) => (prev === m.id ? null : m.id));
              }}
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-semibold">{m.question}</div>
                  <div className="text-xs text-slate-400">
                    Creator: {m.creator_name || users.find((u) => u.id === m.creator_id)?.name || 'Unknown'}
                  </div>
                </div>
                <Tag label={m.status} tone={marketStatusTone(m.status)} />
              </div>
              <div className="text-sm text-slate-300">
                YES: {formatProb(m.price_yes)} | NO: {formatProb(m.price_no)}
              </div>
              <div
                className="mt-2 grid gap-2 md:grid-cols-2"
                onClick={(e) => e.stopPropagation()}
                onMouseDown={(e) => e.stopPropagation()}
              >
                <Button
                  disabled={!authenticated || yesLocked}
                  onClick={(e) => {
                    e.stopPropagation();
                    placeBetMutation.mutate({ marketId: m.id, side: 'YES' });
                  }}
                >
                  Bet 1€ YES
                  <span className="block text-xs opacity-80">
                    {!authenticated
                      ? 'Log in with password'
                      : yesLocked
                      ? 'Locked above 95% YES'
                      : `Win ${m.yes_preview.payout.toFixed(2)}€`}
                  </span>
                </Button>
                <Button
                  disabled={!authenticated || noLocked}
                  onClick={(e) => {
                    e.stopPropagation();
                    placeBetMutation.mutate({ marketId: m.id, side: 'NO' });
                  }}
                >
                  Bet 1€ NO
                  <span className="block text-xs opacity-80">
                    {!authenticated
                      ? 'Log in with password'
                      : noLocked
                      ? 'Locked below 5% YES'
                      : `Win ${m.no_preview.payout.toFixed(2)}€`}
                  </span>
                </Button>
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  const renderComments = (market: MarketWithBets) => {
    const hasMore = commentsQuery.hasNextPage;
    const loading = commentsQuery.isFetching;
    const authenticated = canActAsUser && Boolean(activeUserPassword);
    return (
      <Card>
        <div className="mb-2 flex items-center justify-between">
          <h4 className="font-semibold">Comments</h4>
          <span className="text-xs text-slate-400">{comments.length} shown</span>
        </div>
        <div className="flex flex-col gap-2">
          {comments.length === 0 && !loading && (
            <div className="text-sm text-slate-400">No comments yet.</div>
          )}
          {comments.map((c) => {
            const canDelete = activeUser?.id === c.user_id;
            return (
              <div key={c.id} className="rounded-lg border border-slate-800 bg-slate-900 p-3">
                <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
                  <strong className="text-slate-100">{users.find((u) => u.id === c.user_id)?.name ?? `User ${c.user_id}`}</strong>
                  {c.is_op ? <Tag label="OP" tone="success" /> : null}
                  <Tag label={`User ${c.user_id}`} />
                  <span>{new Date(c.created_at).toLocaleString()}</span>
                  {canDelete ? (
                    <Button
                      variant="danger"
                      onClick={() => commentDeleteMutation.mutate({ commentId: c.id, marketId: market.id })}
                    >
                      Delete
                    </Button>
                  ) : null}
                </div>
                <div className="mt-2 text-sm">{c.text}</div>
              </div>
            );
          })}
          {hasMore ? (
            <Button
              variant="secondary"
              disabled={loading}
              onClick={() => commentsQuery.fetchNextPage()}
            >
              Load more
            </Button>
          ) : null}
          {authenticated ? (
            <form
              className="mt-2 space-y-2"
              onSubmit={(e) => {
                e.preventDefault();
                const form = new FormData(e.currentTarget);
                const text = (form.get('comment') as string)?.trim();
                if (!text) {
                  alert('Comment cannot be empty');
                  return;
                }
                commentCreateMutation.mutate({ marketId: market.id, text });
                e.currentTarget.reset();
              }}
            >
              <label className="text-sm font-semibold text-slate-200" htmlFor="comment">
                Add a comment
              </label>
              <TextArea id="comment" name="comment" maxLength={280} placeholder="Share a quick note" />
              <Button type="submit">Post comment</Button>
            </form>
          ) : (
            <div className="text-sm text-slate-400">Log in to add a comment.</div>
          )}
        </div>
      </Card>
    );
  };

  const renderMarketDetail = (market: MarketWithBets) => {
    const yesLocked = market.price_yes > 0.95;
    const noLocked = market.price_yes < 0.05;
    const canBet = market.status === 'OPEN' && canActAsUser && Boolean(activeUserPassword);
    const canResolve =
      canActAsUser && activeUser?.id === market.creator_id && !['RESOLVED', 'INVALID'].includes(market.status);

    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/90 p-4 shadow-deep">
        <div className="flex items-start justify-between gap-2">
          <div>
            <div className="text-lg font-semibold">{market.question}</div>
            <div className="text-sm text-slate-400">{market.description || ''}</div>
            <div className="text-xs text-slate-500">
              Created by: {market.creator_name || users.find((u) => u.id === market.creator_id)?.name || 'Unknown'}
            </div>
          </div>
          <Tag label={market.status} tone={marketStatusTone(market.status)} />
        </div>

        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Card>
            <div className="text-xs uppercase text-slate-400">YES probability</div>
            <div className="text-xl font-bold">{formatProb(market.price_yes)}</div>
          </Card>
          <Card>
            <div className="text-xs uppercase text-slate-400">NO probability</div>
            <div className="text-xl font-bold">{formatProb(market.price_no)}</div>
          </Card>
          <Card>
            <div className="text-xs uppercase text-slate-400">Creator</div>
            <div className="text-xl font-bold">
              {market.creator_name || users.find((u) => u.id === market.creator_id)?.name || 'Unknown'}
            </div>
          </Card>
          <Card>
            <div className="text-xs uppercase text-slate-400">Liquidity b</div>
            <div className="text-xl font-bold">{market.liquidity_b}</div>
          </Card>
        </div>

        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <Card>
            <div className="text-xs uppercase text-slate-400">1€ bet preview</div>
            <div>YES: payout {market.yes_preview.payout.toFixed(4)}€</div>
            <div>NO: payout {market.no_preview.payout.toFixed(4)}€</div>
          </Card>
          <Card>
            <div className="text-xs uppercase text-slate-400">Volume</div>
            <div className="text-lg font-semibold">
              YES: {market.volume_yes.toFixed(2)}€ | NO: {market.volume_no.toFixed(2)}€ | Total:{' '}
              {(market.volume_yes + market.volume_no).toFixed(2)}€
            </div>
          </Card>
        </div>

        <div className="mt-4">
          <OddsChart history={market.odds_history} />
        </div>

        {['RESOLVED', 'INVALID'].includes(market.status) ? (
          <Card className="mt-4">
            <div className="text-sm font-semibold">Resolution breakdown</div>
            <div>Total pot: {market.total_pot.toFixed(2)}€</div>
            <div>Creator settlement: {market.creator_payout.toFixed(2)}€</div>
            <div>
              Winning payout: {(market.total_payout_yes + market.total_payout_no).toFixed(2)}€ — Outcome:{' '}
              {market.outcome}
            </div>
            <div className="mt-2">
              <div className="text-sm font-semibold">Payouts</div>
              <div className="max-h-64 overflow-auto rounded-lg border border-slate-800">
                {market.payouts.length ? (
                  market.payouts.map((payout, idx) => (
                    <ListRow key={`${payout.user_id}-${idx}`}>
                      <div className="flex items-center justify-between text-sm">
                        <Tag label={payout.entry_type} />
                        <span>
                          {users.find((u) => u.id === payout.user_id)?.name ?? `User ${payout.user_id}`}
                        </span>
                      </div>
                      <div className="text-sm">
                        {payout.amount.toFixed(2)}€ {payout.note ? `— ${payout.note}` : ''}
                      </div>
                    </ListRow>
                  ))
                ) : (
                  <div className="p-2 text-sm text-slate-400">No payouts yet</div>
                )}
              </div>
            </div>
          </Card>
        ) : null}

        <div className="mt-4 grid gap-2 md:grid-cols-2">
          <Button
            disabled={!canBet || yesLocked}
            onClick={() => placeBetMutation.mutate({ marketId: market.id, side: 'YES' })}
          >
            Bet 1€ YES
            <span className="block text-xs opacity-80">
              {!canActAsUser
                ? 'Log in with password'
                : yesLocked
                ? 'Locked above 95% YES'
                : `Win ${market.yes_preview.payout.toFixed(2)}€`}
            </span>
          </Button>
          <Button
            disabled={!canBet || noLocked}
            onClick={() => placeBetMutation.mutate({ marketId: market.id, side: 'NO' })}
          >
            Bet 1€ NO
            <span className="block text-xs opacity-80">
              {!canActAsUser
                ? 'Log in with password'
                : noLocked
                ? 'Locked below 5% YES'
                : `Win ${market.no_preview.payout.toFixed(2)}€`}
            </span>
          </Button>
          {canResolve ? (
            <>
              <Button variant="secondary" onClick={() => resolveMarketMutation.mutate({ marketId: market.id, outcome: 'YES' })}>
                Resolve YES
              </Button>
              <Button variant="secondary" onClick={() => resolveMarketMutation.mutate({ marketId: market.id, outcome: 'NO' })}>
                Resolve NO
              </Button>
              <Button variant="danger" onClick={() => deleteMarketMutation.mutate(market.id)}>
                Delete & clear
              </Button>
            </>
          ) : null}
        </div>

        <div className="mt-4">
          <div className="text-sm font-semibold">Bets</div>
          <div className="max-h-64 overflow-auto rounded-lg border border-slate-800">
            {market.bets.length ? (
              market.bets.map((b) => (
                <ListRow key={b.id}>
                  <div className="flex items-center justify-between text-xs text-slate-400">
                    <span>
                      <Tag label={b.side} />
                    </span>
                    <span>{new Date(b.placed_at).toLocaleString()}</span>
                  </div>
                  <div className="text-sm">
                    Stake: {b.cost.toFixed(2)}€ | Shares: {b.shares.toFixed(4)}
                  </div>
                </ListRow>
              ))
            ) : (
              <div className="p-2 text-sm text-slate-400">No bets yet</div>
            )}
          </div>
        </div>

        <div className="mt-4">{renderComments(market)}</div>
      </div>
    );
  };

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-slate-800 bg-slate-950/90 px-6 py-4 shadow-lg backdrop-blur">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold">Friends-only Prediction Market</h1>
            <div className="text-sm text-slate-400">
              API base: <code className="text-xs text-cyan-300">{API_BASE}</code>
            </div>
          </div>
          <Chip label={authLabel} ghost={!isAdmin && !isLoggedIn} />
        </div>
      </header>

      <main className="mx-auto grid max-w-6xl grid-cols-1 gap-4 px-4 py-6 lg:grid-cols-[320px,1fr]">
        <section className="flex flex-col gap-4">
          <Card className="bg-gradient-to-br from-slate-900 to-slate-950">
            <div className="mb-2 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold">Log in</h2>
                <div className="text-sm text-slate-400">Sign in with your username to unlock the market.</div>
              </div>
              <Chip label={authLabel} ghost={!isAdmin && !isLoggedIn} />
            </div>
            <form className="space-y-2" onSubmit={handleLogin}>
              <label className="text-sm font-semibold text-slate-200" htmlFor="login-username">
                Username
              </label>
              <Input id="login-username" name="username" placeholder="e.g. Alice" autoComplete="username" />
              <label className="text-sm font-semibold text-slate-200" htmlFor="login-password">
                Password
              </label>
              <Input
                id="login-password"
                name="password"
                type="password"
                placeholder="Paste your password"
                autoComplete="current-password"
              />
              <div className="flex items-center gap-2">
                <Button type="submit" disabled={loginMutation.isPending}>
                  {loginMutation.isPending ? 'Signing in…' : 'Start session'}
                </Button>
                <Button variant="secondary" onClick={handleLogout} disabled={!isAdmin && !isLoggedIn}>
                  Log out
                </Button>
              </div>
            </form>
            <div className="mt-2 text-sm text-slate-400">
              {isAdmin
                ? 'Admin session active. User access disabled.'
                : isLoggedIn
                ? `Logged in as ${activeUser?.name}.`
                : 'Waiting for login.'}
            </div>
            {isLoggedIn && !isAdmin ? (
              <div className="mt-3 grid grid-cols-2 gap-2">
                <Card>
                  <div className="text-xs uppercase text-slate-400">Balance</div>
                  <div className="text-xl font-bold">
                    {activeUserQuery.data ? `${activeUserQuery.data.balance.toFixed(2)} €` : '–'}
                  </div>
                </Card>
                <Card>
                  <div className="text-xs uppercase text-slate-400">Positions</div>
                  <div className="text-xl font-bold">{userPositions.length}</div>
                </Card>
              </div>
            ) : null}
          </Card>

          <Card className="border-blue-800 bg-gradient-to-br from-slate-950 to-slate-900">
            <div className="mb-2 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold">Admin console</h3>
                <div className="text-sm text-slate-400">Manage users and share credentials.</div>
              </div>
              <Chip label={isAdmin ? 'Admin online' : 'Locked'} ghost={!isAdmin} />
            </div>
            <div className="text-sm text-slate-400">
              {isAdmin ? 'Admin unlocked as admin/admin.' : 'Log in as admin/admin in the main form to unlock controls.'}
            </div>
            <div className="mt-2 flex items-center gap-2">
              <Button variant="secondary" disabled={!isAdmin} onClick={() => setAdminSession({ authenticated: false, username: '', password: '' })}>
                Log out admin
              </Button>
            </div>

            {isAdmin ? (
              <div className="mt-3 space-y-3">
                <div className="flex flex-col gap-2">
                  <div className="flex gap-2">
                    <Input placeholder="New user name" id="new-user-name" name="new-user-name" />
                    <Button
                      onClick={() => {
                        const input = document.getElementById('new-user-name') as HTMLInputElement | null;
                        const name = input?.value.trim() || '';
                        if (!name) return alert('Enter a name');
                        createUserMutation.mutate(name);
                        if (input) input.value = '';
                      }}
                    >
                      Create user
                    </Button>
                  </div>
                  <div className="text-xs text-slate-400">New users start with 50€ and a fresh password.</div>
                  {lastCreatedPassword ? (
                    <div className="rounded-lg border border-amber-500 bg-amber-950/40 p-2 text-sm text-amber-100">
                      Password for last created user: <strong>{lastCreatedPassword}</strong>
                    </div>
                  ) : null}
                </div>

                <div>
                  <label className="text-sm font-semibold text-slate-200">Manage user</label>
                  <select
                    className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-900 px-3 py-2 text-slate-100"
                    id="admin-user-select"
                    onChange={() => setLastCreatedPassword(null)}
                  >
                    <option value="">Select user</option>
                    {users.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.name} (ID {u.id})
                      </option>
                    ))}
                  </select>
                  <div className="text-xs text-slate-400">Applies to balance updates and deletions.</div>
                </div>

                <Card className="border-slate-800 bg-slate-950">
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <div className="text-xs uppercase text-slate-400">Balances</div>
                      <div className="text-xs text-slate-400">Top up the selected account directly.</div>
                    </div>
                    <Input id="topup-amount" type="number" defaultValue={10} min={1} />
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Button
                      variant="secondary"
                      onClick={() => {
                        const select = document.getElementById('admin-user-select') as HTMLSelectElement | null;
                        const targetId = Number(select?.value || '');
                        const amount = Number((document.getElementById('topup-amount') as HTMLInputElement | null)?.value || '0');
                        if (!targetId) return alert('Select a user');
                        if (amount <= 0) return alert('Enter a positive amount');
                        depositMutation.mutate({ userId: targetId, amount });
                      }}
                    >
                      Top up selected user
                    </Button>
                    <Button
                      variant="danger"
                      onClick={() => {
                        const select = document.getElementById('admin-user-select') as HTMLSelectElement | null;
                        const targetId = Number(select?.value || '');
                        if (!targetId) return alert('Pick a user to delete.');
                        if (!confirm('Delete this user account? Markets must be cleared and no bets outstanding.')) return;
                        deleteUserMutation.mutate(targetId);
                      }}
                    >
                      Delete selected user
                    </Button>
                  </div>
                </Card>

                <Card className="border-slate-800 bg-slate-950">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-xs uppercase text-slate-400">Platform</div>
                      <div className="text-xs text-slate-400">Maintenance tools</div>
                    </div>
                    <Button
                      variant="danger"
                      onClick={() => {
                        if (!confirm('This will delete all users, markets, and bets. Continue?')) return;
                        resetMutation.mutate();
                      }}
                    >
                      Reset platform
                    </Button>
                  </div>
                </Card>

                <div>
                  <h4 className="text-sm font-semibold">User directory</h4>
                  <div className="mt-2 max-h-64 overflow-auto rounded-lg border border-slate-800">
                    {adminDirectoryQuery.data?.length ? (
                      adminDirectoryQuery.data.map((u) => (
                        <ListRow key={u.id}>
                          <div className="flex items-center justify-between text-sm">
                            <strong>{u.name}</strong>
                            <span>ID {u.id}</span>
                          </div>
                          <div className="text-sm">Balance: {u.balance.toFixed(2)}€</div>
                          <div className="text-sm">
                            Password: <Tag label={u.password} />
                          </div>
                        </ListRow>
                      ))
                    ) : (
                      <div className="p-2 text-sm text-slate-400">
                        {adminDirectoryQuery.isFetching
                          ? 'Loading…'
                          : 'No users yet. Create one to share credentials.'}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ) : null}
          </Card>
        </section>

        <section className="space-y-4">
          <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-3 shadow-deep">
            <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
              {(['open', 'positions', 'ledger', 'admin'] as const).map((tab) => (
                <Button
                  key={tab}
                  variant={activeTab === tab ? 'primary' : 'secondary'}
                  onClick={() => setActiveTab(tab)}
                >
                  {tab === 'open'
                    ? 'Open markets'
                    : tab === 'positions'
                    ? 'Open positions'
                    : tab === 'ledger'
                    ? 'Ledger'
                    : 'Market admin'}
                </Button>
              ))}
            </div>
          </div>

          {activeTab === 'open' ? (
            <Card>
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <div>
                  <div className="text-xs uppercase text-slate-400">Active account</div>
                  <div className="text-lg font-semibold">{activeUser?.name ?? '–'}</div>
                </div>
                <Button variant="ghost" onClick={() => (isLoggedIn ? setCreateOpen((p) => !p) : alert('Log in to create a market.'))}>
                  <span className="mr-2 rounded-full bg-slate-800 px-2 py-1 text-lg">{createOpen ? '−' : '+'}</span>
                  {createOpen ? 'Hide form' : 'New market'}
                </Button>
              </div>
              {createOpen ? (
                <div className="mb-4 rounded-lg border border-slate-800 bg-slate-950 p-3">
                  <div className="flex flex-wrap items-center justify-between text-xs text-slate-400">
                    <span>Seed: 10€ will be locked from creator.</span>
                    <span>Bet size: fixed 1€</span>
                  </div>
                  <form
                    className="mt-2 grid gap-2"
                    onSubmit={(e) => {
                      e.preventDefault();
                      if (!activeUser) return alert('Log in to create a market.');
                      const form = new FormData(e.currentTarget);
                      const question = (form.get('question') as string)?.trim();
                      const description = (form.get('description') as string)?.trim();
                      const initialProb = Number(form.get('initial-prob') || '0.5');
                      createMarketMutation.mutate({ question, description, initial_prob_yes: initialProb });
                      e.currentTarget.reset();
                    }}
                  >
                    <label className="text-sm font-semibold text-slate-200" htmlFor="question">
                      Question
                    </label>
                    <Input id="question" name="question" placeholder="YES if PSG beats OM?" required />
                    <label className="text-sm font-semibold text-slate-200" htmlFor="description">
                      Details
                    </label>
                    <TextArea id="description" name="description" placeholder="Resolution rules, notes" />
                    <label className="text-sm font-semibold text-slate-200" htmlFor="initial-prob">
                      Initial probability for YES (0-1)
                    </label>
                    <Input
                      id="initial-prob"
                      name="initial-prob"
                      type="number"
                      step="0.01"
                      min="0.1"
                      max="0.9"
                      defaultValue={0.5}
                    />
                    <Button type="submit" disabled={createMarketMutation.isPending}>
                      {createMarketMutation.isPending ? 'Creating…' : 'Create market'}
                    </Button>
                  </form>
                </div>
              ) : null}
              <div>{renderMarketList(openMarkets)}</div>
            </Card>
          ) : null}

          {activeTab === 'positions' ? (
            <Card>
              <div className="mb-2 flex items-center justify-between">
                <h2 className="text-lg font-semibold">Your open positions</h2>
                <Chip label={String(userPositions.length)} ghost />
              </div>
              {renderPositions(userPositions)}
            </Card>
          ) : null}

          {activeTab === 'ledger' ? (
            <Card>
              <div className="mb-2 flex items-center justify-between">
                <h2 className="text-lg font-semibold">Ledger history</h2>
                <Chip
                  label={
                    activeUserQuery.data ? `${activeUserQuery.data.balance.toFixed(2)} €` : '–'
                  }
                  ghost
                />
              </div>
              {renderLedger(userLedger)}
            </Card>
          ) : null}

          {activeTab === 'admin' ? (
            <Card>
              <h2 className="text-lg font-semibold">Market admin</h2>
              <div className="text-sm text-slate-400">Manage the markets you created.</div>
              <div className="mt-3 space-y-3">
                {canActAsUser ? (
                  markets
                    .filter((m) => m.creator_id === activeUser?.id)
                    .map((m) => (
                      <div
                        key={m.id}
                        className="cursor-pointer rounded-xl border border-slate-800 bg-slate-900 p-3 hover:border-slate-700"
                        role="button"
                        tabIndex={0}
                        onClick={() => setSelectedMarketId((prev) => (prev === m.id ? null : m.id))}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ')
                            setSelectedMarketId((prev) => (prev === m.id ? null : m.id));
                        }}
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <div className="font-semibold">{m.question}</div>
                            <div className="text-xs text-slate-400">{m.description || ''}</div>
                          </div>
                          <Tag label={m.status} tone={marketStatusTone(m.status)} />
                        </div>
                        <div className="text-sm text-slate-300">
                          YES: {formatProb(m.price_yes)} | NO: {formatProb(m.price_no)}
                        </div>
                        <div
                          className="mt-2 flex flex-wrap gap-2"
                          onClick={(e) => e.stopPropagation()}
                          onMouseDown={(e) => e.stopPropagation()}
                        >
                          {['RESOLVED', 'INVALID'].includes(m.status) ? (
                            <span className="text-sm text-slate-400">Resolution complete</span>
                          ) : (
                            <>
                              <Button
                                variant="secondary"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  resolveMarketMutation.mutate({ marketId: m.id, outcome: 'YES' });
                                }}
                              >
                                Resolve YES
                              </Button>
                              <Button
                                variant="secondary"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  resolveMarketMutation.mutate({ marketId: m.id, outcome: 'NO' });
                                }}
                              >
                                Resolve NO
                              </Button>
                            </>
                          )}
                          <Button
                            variant="danger"
                            onClick={(e) => {
                              e.stopPropagation();
                              deleteMarketMutation.mutate(m.id);
                            }}
                          >
                            Delete & clear
                          </Button>
                        </div>
                      </div>
                    ))
                ) : (
                  <div className="text-sm text-slate-400">Log in to see the markets you created.</div>
                )}
              </div>
            </Card>
          ) : null}
        </section>
      </main>

      <Modal
        open={selectedMarketId !== null}
        title={selectedMarket?.question ?? 'Market details'}
        onClose={() => setSelectedMarketId(null)}
      >
        {marketDetailQuery.isLoading ? (
          <div className="text-sm text-slate-400">Loading…</div>
        ) : marketDetailQuery.isError ? (
          <div className="rounded-lg border border-rose-700 bg-rose-950/40 p-3 text-sm text-rose-200">
            {(marketDetailQuery.error as Error)?.message ?? 'Could not load market'}
          </div>
        ) : selectedMarket ? (
          renderMarketDetail(selectedMarket)
        ) : (
          <div className="text-sm text-slate-400">No market selected</div>
        )}
      </Modal>
    </div>
  );
}
