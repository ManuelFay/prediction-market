<template>
  <div class="app-shell">
    <header class="app-header surface flex-between">
      <div>
        <h1>Friends Prediction Market</h1>
        <p class="muted small">Vue-powered SPA backed by the FastAPI pricing engine</p>
      </div>
      <div class="flex-between" style="gap: 12px; flex-wrap: wrap">
        <span class="pill" v-if="session">Logged in as {{ session.name }} ({{ session.balance.toFixed(2) }}€)</span>
        <span class="pill ghost" v-else>Not logged in</span>
        <span class="badge" v-if="admin.authenticated">Admin ready</span>
      </div>
    </header>

    <main class="content">
      <aside class="sidebar">
        <section class="surface panel">
          <h2>Log in</h2>
          <label for="login-name">Username</label>
          <input id="login-name" v-model="loginForm.name" placeholder="alice" />
          <label for="login-password">Password</label>
          <input id="login-password" v-model="loginForm.password" type="password" placeholder="Paste password" />
          <button @click="login">Sign in</button>
          <button class="secondary" @click="logout" :disabled="!session">Log out</button>
          <p class="muted small">Passwords are issued on user creation; they are random secrets.</p>
        </section>

        <section class="surface panel soft">
          <h2>Admin tools</h2>
          <div class="form-row">
            <div>
              <label>Admin user</label>
              <input v-model="admin.username" />
            </div>
            <div>
              <label>Admin password</label>
              <input v-model="admin.password" type="password" />
            </div>
          </div>
          <button class="secondary" @click="authenticateAdmin">Authenticate admin</button>
          <hr />
          <label>Create user (admin only)</label>
          <input v-model="newUserName" placeholder="new user name" />
          <button @click="createUser">Create user</button>
          <p class="small muted" v-if="createdPassword">
            Password: <strong>{{ createdPassword }}</strong>
          </p>
          <hr />
          <div class="form-row">
            <div>
              <label>User ID for top-up</label>
              <input v-model.number="adminActions.userId" type="number" placeholder="1" />
            </div>
            <div>
              <label>Amount (€)</label>
              <input v-model.number="adminActions.amount" type="number" min="0" step="0.5" />
            </div>
          </div>
          <button class="secondary" @click="deposit">Top up balance</button>
          <hr />
          <button class="secondary" @click="resetPlatform">Reset demo data</button>
        </section>

        <section class="surface panel">
          <h2>Create market</h2>
          <p class="muted small">Requires an active user to seed liquidity.</p>
          <label>Question</label>
          <input v-model="createForm.question" placeholder="Will it rain tomorrow?" />
          <label>Description</label>
          <textarea v-model="createForm.description" rows="2" />
          <div class="form-row">
            <div>
              <label>YES meaning</label>
              <input v-model="createForm.yes_meaning" />
            </div>
            <div>
              <label>NO meaning</label>
              <input v-model="createForm.no_meaning" />
            </div>
          </div>
          <label>Resolution source</label>
          <input v-model="createForm.resolution_source" placeholder="Who decides the outcome?" />
          <label>Initial YES probability (0.1 - 0.9)</label>
          <input v-model.number="createForm.initial_prob_yes" type="number" min="0.1" max="0.9" step="0.05" />
          <label>Event time (optional)</label>
          <input v-model="createForm.event_time" type="datetime-local" />
          <button @click="createMarket">Launch market</button>
        </section>
      </aside>

      <section class="surface panel">
        <div class="flex-between" style="align-items: center">
          <h2>Markets</h2>
          <button class="secondary inline" @click="loadMarkets">Refresh</button>
        </div>
        <div class="metric-grid">
          <div class="metric">
            <div class="label">Open</div>
            <div class="value">{{ markets.filter((m) => m.status === 'OPEN').length }}</div>
          </div>
          <div class="metric">
            <div class="label">Pending</div>
            <div class="value">{{ markets.filter((m) => m.status === 'PENDING').length }}</div>
          </div>
          <div class="metric">
            <div class="label">Resolved</div>
            <div class="value">{{ markets.filter((m) => m.status === 'RESOLVED').length }}</div>
          </div>
        </div>
        <div v-if="markets.length === 0" class="muted">No markets yet.</div>
        <div v-for="market in markets" :key="market.id" class="market-card">
          <div class="flex-between">
            <div>
              <div class="small muted">#{{ market.id }}</div>
              <strong>{{ market.question }}</strong>
            </div>
            <span :class="['tag', statusClass(market.status)]">{{ market.status }}</span>
          </div>
          <div class="flex-between small">
            <span>YES: {{ (market.price_yes * 100).toFixed(1) }}%</span>
            <span>NO: {{ (market.price_no * 100).toFixed(1) }}%</span>
          </div>
          <div class="market-actions">
            <button class="secondary" @click="selectMarket(market.id)">Open details</button>
            <button @click="placeBet(market.id, 'YES')" :disabled="!session">Bet YES</button>
            <button @click="placeBet(market.id, 'NO')" :disabled="!session">Bet NO</button>
          </div>
        </div>
      </section>

      <section class="surface panel" v-if="selectedMarket">
        <div class="flex-between">
          <h2>Market #{{ selectedMarket.id }} details</h2>
          <button class="secondary inline" @click="selectMarket(selectedMarket.id)">Refresh</button>
        </div>
        <p><strong>{{ selectedMarket.question }}</strong></p>
        <p class="muted">{{ selectedMarket.description }}</p>
        <div class="metric-grid">
          <div class="metric">
            <div class="label">YES price</div>
            <div class="value">{{ (selectedMarket.price_yes * 100).toFixed(1) }}%</div>
          </div>
          <div class="metric">
            <div class="label">NO price</div>
            <div class="value">{{ (selectedMarket.price_no * 100).toFixed(1) }}%</div>
          </div>
          <div class="metric">
            <div class="label">Volume</div>
            <div class="value">{{ (selectedMarket.total_pot || 0).toFixed(2) }}€</div>
          </div>
          <div class="metric">
            <div class="label">Creator</div>
            <div class="value">ID {{ selectedMarket.creator_id }}</div>
          </div>
        </div>
        <div class="form-row">
          <button @click="placeBet(selectedMarket.id, 'YES')" :disabled="!session">Bet YES</button>
          <button @click="placeBet(selectedMarket.id, 'NO')" :disabled="!session">Bet NO</button>
        </div>
        <label>Complain</label>
        <div class="form-row">
          <input v-model="complaint.reason" placeholder="Why is this market wrong?" />
          <button class="secondary" @click="complain(selectedMarket.id)" :disabled="!session">Submit complaint</button>
        </div>
        <label>Resolve outcome</label>
        <div class="form-row">
          <select v-model="resolution.outcome">
            <option value="YES">YES</option>
            <option value="NO">NO</option>
            <option value="INVALID">INVALID</option>
          </select>
          <button class="secondary" @click="resolve(selectedMarket.id)">Resolve</button>
        </div>
        <hr />
        <h3>Bets</h3>
        <div class="bets-list">
          <div v-if="!selectedMarket.bets.length" class="list-row muted">No bets yet.</div>
          <div v-for="bet in selectedMarket.bets" :key="bet.id" class="list-row small">
            <div class="flex-between">
              <span class="pill ghost">{{ bet.side }}</span>
              <span>{{ new Date(bet.placed_at).toLocaleString() }}</span>
            </div>
            <div>
              Stake: {{ bet.cost.toFixed(2) }}€ • Shares: {{ bet.shares.toFixed(4) }} • User {{ bet.user_id }}
            </div>
          </div>
        </div>
        <h3>Payouts</h3>
        <div class="bets-list">
          <div v-if="!selectedMarket.payouts?.length" class="list-row muted">No payouts yet.</div>
          <div v-for="payout in selectedMarket.payouts" :key="payout.user_id" class="list-row small">
            <div class="flex-between">
              <span>User {{ payout.user_id }}</span>
              <span class="tag">{{ payout.entry_type }}</span>
            </div>
            <div>{{ payout.amount.toFixed(2) }}€ <span v-if="payout.note">— {{ payout.note }}</span></div>
          </div>
        </div>
      </section>

      <section class="surface panel" v-if="session">
        <div class="flex-between">
          <h2>Positions & ledger</h2>
          <button class="secondary inline" @click="refreshUser">Refresh</button>
        </div>
        <h3>Open positions</h3>
        <div class="bets-list">
          <div v-if="positions.length === 0" class="list-row muted">No positions yet.</div>
          <div v-for="pos in positions" :key="pos.market_id" class="list-row small">
            <div class="flex-between">
              <strong>{{ pos.market_question }}</strong>
              <span class="tag">{{ pos.market_status }}</span>
            </div>
            <div>Side: <span class="pill ghost">{{ pos.side }}</span></div>
            <div>
              Shares: {{ pos.total_shares.toFixed(4) }} | Stake: {{ pos.total_stake.toFixed(2) }}€ | Avg prob:
              {{ (pos.avg_odds * 100).toFixed(2) }}% | Potential: {{ pos.potential_payout.toFixed(2) }}€
            </div>
          </div>
        </div>
        <h3>Ledger</h3>
        <div class="ledger-list">
          <div v-if="ledger.length === 0" class="list-row muted">No ledger entries yet.</div>
          <div v-for="entry in ledger" :key="entry.id" class="list-row small">
            <div class="flex-between">
              <span class="tag">{{ entry.entry_type }}</span>
              <span>{{ new Date(entry.created_at).toLocaleString() }}</span>
            </div>
            <div>{{ entry.amount.toFixed(2) }} €<span v-if="entry.note"> — {{ entry.note }}</span></div>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';

interface UserAuth {
  id: number;
  name: string;
  balance: number;
  password: string;
}

interface UserRead {
  id: number;
  name: string;
  balance: number;
}

interface BetPreview {
  payout: number;
  probability: number;
}

interface MarketRead {
  id: number;
  question: string;
  description?: string | null;
  yes_meaning?: string | null;
  no_meaning?: string | null;
  resolution_source?: string | null;
  initial_prob_yes: number;
  liquidity_b: number;
  q_yes: number;
  q_no: number;
  status: string;
  outcome?: string | null;
  created_at: string;
  event_time?: string | null;
  creator_id: number;
  creator_name?: string;
  price_yes: number;
  price_no: number;
  last_bet_at?: string | null;
  yes_preview: BetPreview;
  no_preview: BetPreview;
  total_pot?: number;
  total_payout_yes?: number;
  total_payout_no?: number;
  creator_payout?: number;
  is_deleted?: boolean;
}

interface BetRead {
  id: number;
  user_id: number;
  market_id: number;
  side: string;
  shares: number;
  cost: number;
  placed_at: string;
  implied_odds: number;
}

interface PayoutBreakdown {
  user_id: number;
  amount: number;
  entry_type: string;
  note?: string | null;
}

interface MarketWithBets extends MarketRead {
  bets: BetRead[];
  odds_history: { price_yes: number; price_no: number; timestamp: string }[];
  volume_yes: number;
  volume_no: number;
  payouts: PayoutBreakdown[];
}

interface PositionRead {
  market_id: number;
  market_question: string;
  side: string;
  total_shares: number;
  total_stake: number;
  avg_odds: number;
  potential_payout: number;
  market_status: string;
  market_outcome?: string | null;
}

interface LedgerEntryRead {
  id: number;
  user_id: number;
  market_id?: number | null;
  amount: number;
  entry_type: string;
  created_at: string;
  note?: string | null;
}

const apiBase = import.meta.env.VITE_API_BASE || '';

const session = ref<UserAuth | null>(null);
const loginForm = reactive({ name: '', password: '' });
const markets = ref<MarketRead[]>([]);
const selectedMarket = ref<MarketWithBets | null>(null);
const positions = ref<PositionRead[]>([]);
const ledger = ref<LedgerEntryRead[]>([]);
const newUserName = ref('');
const createdPassword = ref('');
const admin = reactive({ username: 'admin', password: 'admin', authenticated: false });
const adminActions = reactive({ userId: 0, amount: 10 });
const createForm = reactive({
  question: '',
  description: '',
  yes_meaning: '',
  no_meaning: '',
  resolution_source: '',
  initial_prob_yes: 0.5,
  event_time: '',
});
const complaint = reactive({ reason: '' });
const resolution = reactive({ outcome: 'YES' });

const jsonHeaders = { 'Content-Type': 'application/json' };

function adminHeaders() {
  if (!admin.authenticated) return {};
  const token = btoa(`${admin.username}:${admin.password}`);
  return { Authorization: `Basic ${token}` };
}

async function request<T>(path: string, options: RequestInit = {}) {
  const res = await fetch(`${apiBase}${path}`, {
    ...options,
    headers: { ...jsonHeaders, ...(options.headers || {}) },
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error(error.detail || 'Request failed');
  }
  if (res.status === 204) return null as T;
  return (await res.json()) as T;
}

async function login() {
  if (!loginForm.name || !loginForm.password) return alert('Enter username and password');
  try {
    const user = await request<UserAuth>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ name: loginForm.name, password: loginForm.password }),
    });
    session.value = user;
    createdPassword.value = '';
    await refreshUser();
  } catch (err) {
    alert((err as Error).message);
  }
}

function logout() {
  session.value = null;
  positions.value = [];
  ledger.value = [];
}

async function authenticateAdmin() {
  try {
    await request('/admin/users', { headers: adminHeaders() });
    admin.authenticated = true;
  } catch (err) {
    admin.authenticated = false;
    alert('Admin authentication failed');
  }
}

async function createUser() {
  if (!admin.authenticated) return alert('Authenticate admin first');
  if (!newUserName.value.trim()) return alert('Enter a user name');
  try {
    const user = await request<UserAuth>('/users', {
      method: 'POST',
      headers: adminHeaders(),
      body: JSON.stringify({ name: newUserName.value.trim() }),
    });
    createdPassword.value = user.password;
    newUserName.value = '';
    session.value = user;
    loginForm.name = user.name;
    loginForm.password = user.password;
    await refreshUser();
    await loadMarkets();
  } catch (err) {
    alert((err as Error).message);
  }
}

async function deposit() {
  if (!admin.authenticated) return alert('Authenticate admin first');
  if (!adminActions.userId || adminActions.amount <= 0) return alert('Provide user ID and amount');
  try {
    await request(`/users/${adminActions.userId}/deposit`, {
      method: 'POST',
      headers: adminHeaders(),
      body: JSON.stringify({ amount: adminActions.amount }),
    });
    if (session.value && session.value.id === adminActions.userId) await refreshUser();
  } catch (err) {
    alert((err as Error).message);
  }
}

async function resetPlatform() {
  if (!admin.authenticated) return alert('Authenticate admin first');
  if (!confirm('Reset all users, markets, and bets?')) return;
  try {
    await request('/reset', { method: 'POST', headers: adminHeaders() });
    logout();
    markets.value = [];
    selectedMarket.value = null;
    createdPassword.value = '';
    await loadMarkets();
  } catch (err) {
    alert((err as Error).message);
  }
}

async function loadMarkets() {
  try {
    markets.value = await request<MarketRead[]>('/markets');
  } catch (err) {
    alert((err as Error).message);
  }
}

function statusClass(status: string) {
  if (status === 'RESOLVED') return 'success';
  if (status === 'INVALID') return 'danger';
  return '';
}

async function selectMarket(id: number) {
  try {
    selectedMarket.value = await request<MarketWithBets>(`/markets/${id}`);
  } catch (err) {
    alert((err as Error).message);
  }
}

async function createMarket() {
  if (!session.value) return alert('Log in as a user first');
  if (!createForm.question.trim()) return alert('Enter a market question');
  try {
    await request(`/markets?user_id=${session.value.id}`, {
      method: 'POST',
      body: JSON.stringify({
        ...createForm,
        event_time: createForm.event_time ? new Date(createForm.event_time).toISOString() : null,
      }),
    });
    await loadMarkets();
  } catch (err) {
    alert((err as Error).message);
  }
}

async function placeBet(marketId: number, side: string) {
  if (!session.value) return alert('Log in first');
  try {
    await request(`/markets/${marketId}/bet?user_id=${session.value.id}`, {
      method: 'POST',
      body: JSON.stringify({ side, password: session.value.password }),
    });
    await refreshUser();
    await selectMarket(marketId);
    await loadMarkets();
  } catch (err) {
    alert((err as Error).message);
  }
}

async function complain(marketId: number) {
  if (!session.value) return alert('Log in first');
  if (!complaint.reason.trim()) return alert('Enter a complaint reason');
  try {
    await request(`/markets/${marketId}/complain`, {
      method: 'POST',
      body: JSON.stringify({ reason: complaint.reason }),
    });
    complaint.reason = '';
    await selectMarket(marketId);
  } catch (err) {
    alert((err as Error).message);
  }
}

async function resolve(marketId: number) {
  try {
    await request(`/markets/${marketId}/resolve`, {
      method: 'POST',
      body: JSON.stringify({ outcome: resolution.outcome }),
    });
    await selectMarket(marketId);
    await refreshUser();
    await loadMarkets();
  } catch (err) {
    alert((err as Error).message);
  }
}

async function refreshUser() {
  if (!session.value) return;
  try {
    const user = await request<UserAuth>(`/auth/login`, {
      method: 'POST',
      body: JSON.stringify({ name: session.value.name, password: session.value.password }),
    });
    session.value = user;
    positions.value = await request<PositionRead[]>(`/users/${user.id}/positions`);
    ledger.value = await request<LedgerEntryRead[]>(`/users/${user.id}/ledger`);
  } catch (err) {
    alert((err as Error).message);
  }
}

onMounted(async () => {
  await loadMarkets();
});
</script>
