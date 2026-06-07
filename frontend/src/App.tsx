import {
  Activity,
  Archive,
  Bot,
  CheckCircle2,
  Clipboard,
  Database,
  FileText,
  History,
  LayoutDashboard,
  Loader2,
  Lock,
  LogOut,
  MessageSquare,
  RefreshCw,
  Search,
  Send,
  Settings,
  ShieldCheck,
  Table2,
  UploadCloud,
} from "lucide-react";
import { type FormEvent, type ReactNode, useEffect, useMemo, useState } from "react";

import {
  archiveChatSession,
  askQuestion,
  getChatSession,
  getCurrentUser,
  listChatSessions,
  login,
  logout,
} from "./api";
import type { AskResponse, AuthUser, ChatMessage, ChatSession } from "./types";

const authStorageKey = "enterprise-data-copilot.auth";

const sampleQuestions = [
  "Available stock of material MAT0006",
  "committed quantity of PO1001",
  "Who is supplier of PO1001?",
  "What is the reimbursement limit for meals?",
  "What data must not be shared in chat or email?",
];

type StoredAuth = {
  access: string;
  refresh: string;
  sessionId: string;
};

type WorkspaceView = "dashboard" | "chat" | "sessions" | "data" | "documents" | "audit" | "sql";

function App() {
  const [auth, setAuth] = useState<StoredAuth | null>(() => readStoredAuth());
  const [user, setUser] = useState<AuthUser | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [view, setView] = useState<WorkspaceView>("dashboard");
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState(sampleQuestions[0]);
  const [limit, setLimit] = useState(5);
  const [lastResponse, setLastResponse] = useState<AskResponse | null>(null);
  const [detailTab, setDetailTab] = useState<"sql" | "rows" | "sources" | "metadata">("sql");
  const [isLoading, setIsLoading] = useState(false);
  const [isSigningIn, setIsSigningIn] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isSuperUser = Boolean(user?.is_superuser);
  const token = auth?.access ?? "";
  const canCallApi = token.length > 0;

  useEffect(() => {
    if (!auth?.access) return;
    void loadProfileAndSessions(auth.access);
  }, [auth?.access]);

  async function loadProfileAndSessions(accessToken: string) {
    setError(null);
    try {
      const profile = await getCurrentUser(accessToken);
      setUser(profile);
      const nextSessions = await listChatSessions(accessToken);
      setSessions(nextSessions);
    } catch (nextError) {
      setError(getErrorMessage(nextError));
    }
  }

  async function submitLogin(event: FormEvent) {
    event.preventDefault();
    if (!username.trim() || !password) return;

    setIsSigningIn(true);
    setError(null);
    try {
      const session = await login({ username: username.trim(), password });
      const nextAuth = {
        access: session.access,
        refresh: session.refresh,
        sessionId: session.session_id,
      };
      localStorage.setItem(authStorageKey, JSON.stringify(nextAuth));
      setAuth(nextAuth);
      setPassword("");
      setView("dashboard");
    } catch (nextError) {
      setError(getErrorMessage(nextError));
    } finally {
      setIsSigningIn(false);
    }
  }

  async function signOut() {
    const currentAuth = auth;
    clearAuthState();
    if (!currentAuth) return;

    try {
      await logout({
        token: currentAuth.access,
        refresh: currentAuth.refresh,
        sessionId: currentAuth.sessionId,
      });
    } catch {
      // Local logout should still succeed if the server session is already expired.
    }
  }

  async function refreshSessions() {
    if (!canCallApi) return;
    setError(null);
    try {
      const nextSessions = await listChatSessions(token);
      setSessions(nextSessions);
    } catch (nextError) {
      setError(getErrorMessage(nextError));
    }
  }

  async function loadSession(sessionId: string) {
    setError(null);
    setActiveSessionId(sessionId);
    setView("chat");
    try {
      const detail = await getChatSession(token, sessionId);
      setMessages(detail.messages);
      setLastResponse(null);
    } catch (nextError) {
      setError(getErrorMessage(nextError));
    }
  }

  async function submitQuestion(event: FormEvent) {
    event.preventDefault();
    if (!canCallApi || !question.trim()) return;

    const askedQuestion = question.trim();
    setIsLoading(true);
    setError(null);
    setView("chat");
    setMessages((current) => [
      ...current,
      {
        id: Date.now(),
        role: "USER",
        content: askedQuestion,
        metadata: {},
        created_at: new Date().toISOString(),
      },
    ]);

    try {
      const response = await askQuestion({
        token,
        question: askedQuestion,
        sessionId: activeSessionId,
        limit,
      });
      setLastResponse(response);
      setDetailTab(response.answer_source === "policy" ? "sources" : "sql");
      if (response.session_id) {
        setActiveSessionId(response.session_id);
      }
      setMessages((current) => [
        ...current,
        {
          id: response.assistant_message_id ?? Date.now() + 1,
          role: "ASSISTANT",
          content: response.answer,
          metadata: {
            answer_source: response.answer_source,
            row_count: response.row_count,
            cache_hit: response.cache_hit,
            workflow_run_id: response.workflow_run_id,
          },
          created_at: new Date().toISOString(),
        },
      ]);
      setQuestion("");
      await refreshSessions();
    } catch (nextError) {
      setError(getErrorMessage(nextError));
    } finally {
      setIsLoading(false);
    }
  }

  async function archiveActiveSession() {
    if (!activeSessionId) return;
    setError(null);
    try {
      await archiveChatSession(token, activeSessionId);
      setActiveSessionId(null);
      setMessages([]);
      setLastResponse(null);
      await refreshSessions();
    } catch (nextError) {
      setError(getErrorMessage(nextError));
    }
  }

  function startNewChat() {
    setActiveSessionId(null);
    setMessages([]);
    setLastResponse(null);
    setView("chat");
  }

  function clearAuthState() {
    localStorage.removeItem(authStorageKey);
    setAuth(null);
    setUser(null);
    setSessions([]);
    setMessages([]);
    setActiveSessionId(null);
    setLastResponse(null);
    setView("dashboard");
  }

  const activeSessionTitle = useMemo(() => {
    return sessions.find((session) => session.session_id === activeSessionId)?.title ?? "New chat";
  }, [activeSessionId, sessions]);

  const stats = useMemo(() => buildStats(sessions, lastResponse), [sessions, lastResponse]);

  if (!auth) {
    return (
      <main className="grid min-h-screen place-items-center bg-panel px-5 text-ink">
        <section className="w-full max-w-md rounded border border-line bg-white p-6 shadow-surface">
          <div className="mb-6 flex items-center gap-3">
            <div className="grid h-11 w-11 place-items-center rounded bg-ink text-white">
              <Bot size={24} aria-hidden="true" />
            </div>
            <div>
              <h1 className="text-xl font-semibold">Enterprise Data Copilot</h1>
              <p className="text-sm text-slate-500">Sign in to ask data and policy questions</p>
            </div>
          </div>

          {error ? <Alert message={error} /> : null}

          <form onSubmit={submitLogin} className="space-y-4">
            <label className="block text-sm font-medium">
              Username
              <input
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                className="mt-2 w-full rounded border border-line px-3 py-2 outline-none transition focus:border-accent focus:ring-2 focus:ring-blue-100"
                autoComplete="username"
              />
            </label>
            <label className="block text-sm font-medium">
              Password
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="mt-2 w-full rounded border border-line px-3 py-2 outline-none transition focus:border-accent focus:ring-2 focus:ring-blue-100"
                autoComplete="current-password"
              />
            </label>
            <button type="submit" className="btn-primary w-full" disabled={isSigningIn}>
              {isSigningIn ? <Loader2 size={16} className="animate-spin" /> : <Lock size={16} />}
              Login
            </button>
          </form>
        </section>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-panel text-ink">
      <div className="grid min-h-screen grid-cols-1 xl:grid-cols-[280px_minmax(0,1fr)]">
        <aside className="border-b border-line bg-white xl:border-b-0 xl:border-r">
          <div className="flex h-full flex-col">
            <div className="border-b border-line px-5 py-5">
              <div className="flex items-center gap-3">
                <div className="grid h-10 w-10 place-items-center rounded bg-ink text-white">
                  <Bot size={22} aria-hidden="true" />
                </div>
                <div>
                  <h1 className="text-lg font-semibold">Enterprise Data Copilot</h1>
                  <p className="text-sm text-slate-500">Read-only data assistant</p>
                </div>
              </div>
            </div>

            <div className="border-b border-line px-5 py-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold">{user?.username ?? "Loading user"}</div>
                  <div className="mt-1">
                    <RoleBadge isSuperUser={isSuperUser} />
                  </div>
                </div>
                <button type="button" className="icon-button" onClick={() => void signOut()} title="Logout">
                  <LogOut size={16} aria-hidden="true" />
                </button>
              </div>
            </div>

            <nav className="space-y-1 px-3 py-4">
              <NavButton active={view === "dashboard"} icon={<LayoutDashboard size={17} />} onClick={() => setView("dashboard")}>
                Dashboard
              </NavButton>
              <NavButton active={view === "chat"} icon={<MessageSquare size={17} />} onClick={startNewChat}>
                Ask Copilot
              </NavButton>
              <NavButton active={view === "sessions"} icon={<History size={17} />} onClick={() => setView("sessions")}>
                Sessions
              </NavButton>
              <NavButton active={view === "data"} icon={<Table2 size={17} />} onClick={() => setView("data")}>
                Data Explorer
              </NavButton>
              {isSuperUser ? (
                <>
                  <NavButton active={view === "documents"} icon={<UploadCloud size={17} />} onClick={() => setView("documents")}>
                    Documents
                  </NavButton>
                  <NavButton active={view === "audit"} icon={<Activity size={17} />} onClick={() => setView("audit")}>
                    Audit Logs
                  </NavButton>
                  <NavButton active={view === "sql"} icon={<Database size={17} />} onClick={() => setView("sql")}>
                    SQL Review
                  </NavButton>
                </>
              ) : null}
            </nav>

            <div className="mt-auto border-t border-line p-4 text-xs leading-5 text-slate-500">
              Staff can ask questions and view their sessions. Super Users can inspect SQL,
              logs, document indexing, and all operational details.
            </div>
          </div>
        </aside>

        <section className="flex min-h-screen flex-col">
          <header className="flex flex-col gap-3 border-b border-line bg-white px-5 py-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <div className="text-sm text-slate-500">{getViewKicker(view, isSuperUser)}</div>
              <h2 className="text-xl font-semibold">{getViewTitle(view, activeSessionTitle)}</h2>
            </div>
            <div className="flex flex-wrap gap-2">
              <button type="button" className="btn-secondary" onClick={() => void refreshSessions()}>
                <RefreshCw size={16} aria-hidden="true" />
                Refresh
              </button>
              <button type="button" className="btn-primary" onClick={startNewChat}>
                <MessageSquare size={16} aria-hidden="true" />
                New Chat
              </button>
            </div>
          </header>

          {error ? <Alert message={error} /> : null}

          {view === "dashboard" ? (
            <Dashboard
              isSuperUser={isSuperUser}
              sessions={sessions}
              stats={stats}
              onOpenChat={startNewChat}
              onOpenSessions={() => setView("sessions")}
            />
          ) : null}
          {view === "chat" ? (
            <ChatWorkspace
              activeSessionId={activeSessionId}
              detailTab={detailTab}
              isLoading={isLoading}
              isSuperUser={isSuperUser}
              lastResponse={lastResponse}
              limit={limit}
              messages={messages}
              question={question}
              onArchive={() => void archiveActiveSession()}
              onDetailTabChange={setDetailTab}
              onLimitChange={setLimit}
              onQuestionChange={setQuestion}
              onSubmit={submitQuestion}
            />
          ) : null}
          {view === "sessions" ? (
            <SessionsView
              sessions={sessions}
              isSuperUser={isSuperUser}
              onLoadSession={(sessionId) => void loadSession(sessionId)}
            />
          ) : null}
          {view === "data" ? <PlaceholderView kind="data" isSuperUser={isSuperUser} /> : null}
          {view === "documents" && isSuperUser ? <PlaceholderView kind="documents" isSuperUser /> : null}
          {view === "audit" && isSuperUser ? <PlaceholderView kind="audit" isSuperUser /> : null}
          {view === "sql" && isSuperUser ? (
            <SqlReviewPreview response={lastResponse} />
          ) : null}
        </section>
      </div>
    </main>
  );
}

function Dashboard({
  isSuperUser,
  sessions,
  stats,
  onOpenChat,
  onOpenSessions,
}: {
  isSuperUser: boolean;
  sessions: ChatSession[];
  stats: ReturnType<typeof buildStats>;
  onOpenChat: () => void;
  onOpenSessions: () => void;
}) {
  return (
    <div className="flex-1 overflow-y-auto p-5">
      <div className="grid gap-5">
        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard label="Sessions" value={stats.totalSessions} icon={<History size={18} />} />
          <MetricCard label="Messages" value={stats.totalMessages} icon={<MessageSquare size={18} />} />
          <MetricCard label="Database Answers" value={stats.databaseAnswers} icon={<Database size={18} />} />
          <MetricCard label="Policy Answers" value={stats.policyAnswers} icon={<FileText size={18} />} />
        </section>

        <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="rounded border border-line bg-white">
            <div className="flex items-center justify-between border-b border-line px-4 py-3">
              <div>
                <h3 className="font-semibold">{isSuperUser ? "All Sessions" : "Your Sessions"}</h3>
                <p className="text-sm text-slate-500">Open a previous conversation or begin a new one.</p>
              </div>
              <button type="button" className="btn-secondary" onClick={onOpenSessions}>
                <Search size={16} aria-hidden="true" />
                Browse
              </button>
            </div>
            <SessionList
              sessions={sessions.slice(0, 6)}
              isSuperUser={isSuperUser}
              onLoadSession={() => undefined}
              compact
            />
          </div>

          <div className="rounded border border-line bg-white p-4">
            <h3 className="font-semibold">Access Model</h3>
            <div className="mt-4 space-y-3 text-sm">
              <AccessRow icon={<CheckCircle2 size={16} />} text="Read-only PostgreSQL browsing for allowed data." />
              <AccessRow icon={<ShieldCheck size={16} />} text="Staff only see their own sessions and answer sources." />
              <AccessRow
                icon={<Settings size={16} />}
                text={
                  isSuperUser
                    ? "Super User tools enabled for documents, audit logs, and SQL review."
                    : "Admin tools are hidden for Staff users."
                }
              />
            </div>
            <button type="button" className="btn-primary mt-5 w-full" onClick={onOpenChat}>
              <Send size={16} aria-hidden="true" />
              Ask a Question
            </button>
          </div>
        </section>
      </div>
    </div>
  );
}

function ChatWorkspace({
  activeSessionId,
  detailTab,
  isLoading,
  isSuperUser,
  lastResponse,
  limit,
  messages,
  question,
  onArchive,
  onDetailTabChange,
  onLimitChange,
  onQuestionChange,
  onSubmit,
}: {
  activeSessionId: string | null;
  detailTab: "sql" | "rows" | "sources" | "metadata";
  isLoading: boolean;
  isSuperUser: boolean;
  lastResponse: AskResponse | null;
  limit: number;
  messages: ChatMessage[];
  question: string;
  onArchive: () => void;
  onDetailTabChange: (tab: "sql" | "rows" | "sources" | "metadata") => void;
  onLimitChange: (limit: number) => void;
  onQuestionChange: (question: string) => void;
  onSubmit: (event: FormEvent) => void;
}) {
  return (
    <div className="grid min-h-0 flex-1 grid-cols-1 xl:grid-cols-[minmax(0,1fr)_380px]">
      <section className="flex min-h-0 flex-col">
        <div className="flex justify-end border-b border-line bg-white px-5 py-3">
          <button type="button" className="btn-secondary" onClick={onArchive} disabled={!activeSessionId}>
            <Archive size={16} aria-hidden="true" />
            Archive
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-5">
          <div className="mx-auto flex max-w-4xl flex-col gap-4">
            {messages.length === 0 ? (
              <div className="rounded border border-line bg-white p-6 shadow-surface">
                <div className="mb-4 flex items-center gap-3">
                  <MessageSquare size={20} className="text-accent" aria-hidden="true" />
                  <h3 className="font-semibold">Start with a live data or policy question</h3>
                </div>
                <div className="grid gap-2 sm:grid-cols-2">
                  {sampleQuestions.map((sample) => (
                    <button
                      key={sample}
                      type="button"
                      onClick={() => onQuestionChange(sample)}
                      className="rounded border border-line bg-panel px-3 py-2 text-left text-sm hover:border-accent hover:bg-blue-50"
                    >
                      {sample}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((message) => <MessageBubble key={message.id} message={message} />)
            )}
            {isLoading ? (
              <div className="flex items-center gap-2 text-sm text-slate-500">
                <Loader2 size={16} className="animate-spin" aria-hidden="true" />
                Waiting for answer
              </div>
            ) : null}
          </div>
        </div>

        <form onSubmit={onSubmit} className="border-t border-line bg-white px-5 py-4">
          <div className="mx-auto flex max-w-4xl flex-col gap-3">
            <textarea
              value={question}
              onChange={(event) => onQuestionChange(event.target.value)}
              className="min-h-24 resize-none rounded border border-line p-3 outline-none transition focus:border-accent focus:ring-2 focus:ring-blue-100"
              placeholder="Ask about purchase orders, inventory, suppliers, customers, or company policy"
            />
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <label className="flex items-center gap-3 text-sm text-slate-600">
                Result limit
                <input
                  type="number"
                  min={1}
                  max={50}
                  value={limit}
                  onChange={(event) => onLimitChange(Number(event.target.value))}
                  className="w-20 rounded border border-line px-2 py-1"
                />
              </label>
              <button type="submit" className="btn-primary" disabled={isLoading || !question.trim()}>
                {isLoading ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
                Ask
              </button>
            </div>
          </div>
        </form>
      </section>

      <aside className="border-t border-line bg-white xl:border-l xl:border-t-0">
        <div className="flex h-full flex-col">
          <div className="border-b border-line px-5 py-4">
            <h2 className="text-lg font-semibold">{isSuperUser ? "Answer details" : "Answer source"}</h2>
            <p className="text-sm text-slate-500">
              {isSuperUser ? "SQL, rows, metadata, and citations" : "Staff can see source labels and citations"}
            </p>
          </div>

          {isSuperUser ? (
            <div className="grid grid-cols-4 border-b border-line text-sm">
              <TabButton active={detailTab === "sql"} onClick={() => onDetailTabChange("sql")}>
                SQL
              </TabButton>
              <TabButton active={detailTab === "rows"} onClick={() => onDetailTabChange("rows")}>
                Rows
              </TabButton>
              <TabButton active={detailTab === "sources"} onClick={() => onDetailTabChange("sources")}>
                Sources
              </TabButton>
              <TabButton active={detailTab === "metadata"} onClick={() => onDetailTabChange("metadata")}>
                Meta
              </TabButton>
            </div>
          ) : null}

          <div className="min-h-0 flex-1 overflow-y-auto p-5">
            {isSuperUser ? (
              <DetailPanel response={lastResponse} tab={detailTab} />
            ) : (
              <StaffSourcePanel response={lastResponse} />
            )}
          </div>
        </div>
      </aside>
    </div>
  );
}

function SessionsView({
  sessions,
  isSuperUser,
  onLoadSession,
}: {
  sessions: ChatSession[];
  isSuperUser: boolean;
  onLoadSession: (sessionId: string) => void;
}) {
  return (
    <div className="flex-1 overflow-y-auto p-5">
      <div className="rounded border border-line bg-white">
        <div className="border-b border-line px-4 py-3">
          <h3 className="font-semibold">Session Dashboard</h3>
          <p className="text-sm text-slate-500">Staff see their sessions; Super Users can use this view for global review.</p>
        </div>
        <SessionList sessions={sessions} isSuperUser={isSuperUser} onLoadSession={onLoadSession} />
      </div>
    </div>
  );
}

function PlaceholderView({ kind, isSuperUser }: { kind: "data" | "documents" | "audit"; isSuperUser: boolean }) {
  const content = {
    data: {
      icon: <Table2 size={22} />,
      title: "Read-only Data Explorer",
      body: "Browse approved PostgreSQL tables and views with search, filters, sorting, and pagination. Update actions stay in Django admin only.",
    },
    documents: {
      icon: <UploadCloud size={22} />,
      title: "Document Management",
      body: "Upload policies, review indexing status, re-index documents, inspect chunks, and delete documents from the knowledge base.",
    },
    audit: {
      icon: <Activity size={22} />,
      title: "Audit Logs",
      body: "Track logins, chatbot questions, generated SQL, indexing actions, permission denials, and failures.",
    },
  }[kind];

  return (
    <div className="flex-1 overflow-y-auto p-5">
      <section className="rounded border border-line bg-white p-6">
        <div className="mb-4 flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded bg-blue-50 text-accent">{content.icon}</div>
          <div>
            <h3 className="font-semibold">{content.title}</h3>
            <p className="text-sm text-slate-500">{isSuperUser ? "Super User workspace" : "Staff read-only workspace"}</p>
          </div>
        </div>
        <p className="max-w-2xl text-sm leading-6 text-slate-600">{content.body}</p>
      </section>
    </div>
  );
}

function SqlReviewPreview({ response }: { response: AskResponse | null }) {
  return (
    <div className="flex-1 overflow-y-auto p-5">
      <section className="rounded border border-line bg-white">
        <div className="border-b border-line px-4 py-3">
          <h3 className="font-semibold">SQL Review</h3>
          <p className="text-sm text-slate-500">Generated SQL is visible only to Super Users.</p>
        </div>
        <div className="p-4">
          <DetailBlock icon={<Database size={16} />} title="Latest generated SQL">
            <pre className="overflow-x-auto whitespace-pre-wrap text-xs leading-5">
              {response?.sql ?? "Ask a database question to review generated SQL here."}
            </pre>
          </DetailBlock>
        </div>
      </section>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "USER";
  const source = typeof message.metadata.answer_source === "string" ? message.metadata.answer_source : null;

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded border px-4 py-3 ${
          isUser ? "border-blue-200 bg-blue-50" : "border-line bg-white shadow-surface"
        }`}
      >
        <div className="mb-2 flex flex-wrap items-center gap-2 text-xs font-semibold uppercase text-slate-500">
          {isUser ? <MessageSquare size={14} /> : <Bot size={14} />}
          {message.role}
          {source ? <SourceBadge source={source} /> : null}
        </div>
        <p className="whitespace-pre-wrap text-sm leading-6">{message.content}</p>
      </div>
    </div>
  );
}

function DetailPanel({
  response,
  tab,
}: {
  response: AskResponse | null;
  tab: "sql" | "rows" | "sources" | "metadata";
}) {
  if (!response) {
    return (
      <div className="rounded border border-dashed border-line p-4 text-sm text-slate-500">
        Run a question to inspect generated SQL, rows, policy citations, and metadata.
      </div>
    );
  }

  if (tab === "sql") {
    return (
      <div className="space-y-4">
        <StatusCard response={response} />
        <DetailBlock icon={<Database size={16} />} title="Generated SQL">
          <pre className="overflow-x-auto whitespace-pre-wrap text-xs leading-5">
            {response.sql ?? "No SQL generated for this answer."}
          </pre>
        </DetailBlock>
      </div>
    );
  }

  if (tab === "rows") {
    return (
      <DetailBlock icon={<Table2 size={16} />} title={`Rows (${response.row_count})`}>
        {response.rows.length === 0 ? (
          <p className="text-sm text-slate-500">No rows returned.</p>
        ) : (
          <pre className="overflow-x-auto whitespace-pre-wrap text-xs leading-5">
            {JSON.stringify(response.rows, null, 2)}
          </pre>
        )}
      </DetailBlock>
    );
  }

  if (tab === "sources") {
    return (
      <DetailBlock icon={<FileText size={16} />} title="Policy sources and citations">
        <pre className="overflow-x-auto whitespace-pre-wrap text-xs leading-5">
          {JSON.stringify(
            {
              citations: response.citations,
              policy_sources: response.policy_sources,
            },
            null,
            2,
          )}
        </pre>
      </DetailBlock>
    );
  }

  return (
    <DetailBlock icon={<Clipboard size={16} />} title="Metadata">
      <pre className="overflow-x-auto whitespace-pre-wrap text-xs leading-5">
        {JSON.stringify(response.metadata, null, 2)}
      </pre>
    </DetailBlock>
  );
}

function StaffSourcePanel({ response }: { response: AskResponse | null }) {
  if (!response) {
    return (
      <div className="rounded border border-dashed border-line p-4 text-sm text-slate-500">
        Ask a question to see whether the answer came from PostgreSQL data, policy documents, or both.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="rounded border border-line p-4">
        <div className="mb-2 text-sm text-slate-500">Answer source</div>
        <SourceBadge source={response.answer_source} />
      </div>
      <DetailBlock icon={<FileText size={16} />} title="Visible citations">
        <pre className="overflow-x-auto whitespace-pre-wrap text-xs leading-5">
          {JSON.stringify(response.citations, null, 2)}
        </pre>
      </DetailBlock>
    </div>
  );
}

function StatusCard({ response }: { response: AskResponse }) {
  return (
    <div className="grid gap-2 text-sm">
      <div className="flex items-center justify-between rounded border border-line p-3">
        <span>Source</span>
        <SourceBadge source={response.answer_source} />
      </div>
      <div className="flex items-center justify-between rounded border border-line p-3">
        <span>Cache hit</span>
        <span className="font-semibold">{response.cache_hit ? "Yes" : "No"}</span>
      </div>
      <div className="flex items-center justify-between rounded border border-line p-3">
        <span>Workflow</span>
        <span className="max-w-40 truncate font-mono text-xs">
          {response.workflow_run_id ?? "None"}
        </span>
      </div>
    </div>
  );
}

function SessionList({
  sessions,
  isSuperUser,
  onLoadSession,
  compact = false,
}: {
  sessions: ChatSession[];
  isSuperUser: boolean;
  onLoadSession: (sessionId: string) => void;
  compact?: boolean;
}) {
  if (sessions.length === 0) {
    return (
      <div className="p-4">
        <div className="rounded border border-dashed border-line p-4 text-sm text-slate-500">
          No sessions loaded yet.
        </div>
      </div>
    );
  }

  return (
    <div className="divide-y divide-line">
      {sessions.map((session) => (
        <button
          key={session.session_id}
          type="button"
          onClick={() => onLoadSession(session.session_id)}
          className="grid w-full gap-2 px-4 py-3 text-left transition hover:bg-panel md:grid-cols-[minmax(0,1fr)_120px_120px_140px]"
        >
          <div>
            <div className="line-clamp-1 text-sm font-medium">{session.title}</div>
            {!compact ? (
              <div className="mt-1 font-mono text-xs text-slate-400">{session.session_id}</div>
            ) : null}
          </div>
          <div className="text-sm text-slate-500">
            {isSuperUser ? session.username : "You"}
          </div>
          <div className="text-sm text-slate-500">{session.message_count} messages</div>
          <div className="text-sm text-slate-500">{formatDate(session.updated_at)}</div>
        </button>
      ))}
    </div>
  );
}

function MetricCard({ icon, label, value }: { icon: ReactNode; label: string; value: number }) {
  return (
    <div className="rounded border border-line bg-white p-4">
      <div className="mb-4 flex items-center justify-between text-slate-500">
        <span className="text-sm">{label}</span>
        {icon}
      </div>
      <div className="text-2xl font-semibold">{value}</div>
    </div>
  );
}

function AccessRow({ icon, text }: { icon: ReactNode; text: string }) {
  return (
    <div className="flex gap-3 rounded border border-line p-3">
      <span className="mt-0.5 text-success">{icon}</span>
      <span className="leading-5 text-slate-600">{text}</span>
    </div>
  );
}

function NavButton({
  active,
  children,
  icon,
  onClick,
}: {
  active: boolean;
  children: string;
  icon: ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex w-full items-center gap-3 rounded px-3 py-2 text-left text-sm font-medium transition ${
        active ? "bg-blue-50 text-accent" : "text-slate-600 hover:bg-panel hover:text-ink"
      }`}
    >
      {icon}
      {children}
    </button>
  );
}

function TabButton({
  active,
  children,
  onClick,
}: {
  active: boolean;
  children: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`border-r border-line px-2 py-3 font-medium last:border-r-0 ${
        active ? "bg-blue-50 text-accent" : "bg-white text-slate-500 hover:bg-panel"
      }`}
    >
      {children}
    </button>
  );
}

function DetailBlock({
  icon,
  title,
  children,
}: {
  icon: ReactNode;
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded border border-line bg-white">
      <div className="flex items-center gap-2 border-b border-line px-3 py-2 text-sm font-semibold">
        {icon}
        {title}
      </div>
      <div className="p-3">{children}</div>
    </section>
  );
}

function SourceBadge({ source }: { source: string }) {
  const normalized = source.toLowerCase();
  const className =
    normalized === "policy"
      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : normalized === "database"
        ? "border-blue-200 bg-blue-50 text-blue-700"
        : "border-amber-200 bg-amber-50 text-amber-700";

  return (
    <span className={`inline-flex items-center rounded border px-2 py-1 text-xs font-semibold capitalize ${className}`}>
      {source || "Unknown"}
    </span>
  );
}

function RoleBadge({ isSuperUser }: { isSuperUser: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border px-2 py-1 text-xs font-semibold ${
        isSuperUser
          ? "border-emerald-200 bg-emerald-50 text-emerald-700"
          : "border-slate-200 bg-slate-50 text-slate-600"
      }`}
    >
      <ShieldCheck size={13} aria-hidden="true" />
      {isSuperUser ? "Super User" : "Staff"}
    </span>
  );
}

function Alert({ message }: { message: string }) {
  return <div className="border-b border-red-200 bg-red-50 px-5 py-3 text-sm text-red-700">{message}</div>;
}

function buildStats(sessions: ChatSession[], response: AskResponse | null) {
  return {
    totalSessions: sessions.length,
    totalMessages: sessions.reduce((total, session) => total + session.message_count, 0),
    databaseAnswers: response?.answer_source === "database" ? 1 : 0,
    policyAnswers: response?.answer_source === "policy" ? 1 : 0,
  };
}

function getViewKicker(view: WorkspaceView, isSuperUser: boolean) {
  if (view === "dashboard") return isSuperUser ? "Super User overview" : "Staff overview";
  if (view === "chat") return "Current session";
  if (view === "sessions") return "Session history";
  if (view === "data") return "Read-only PostgreSQL";
  if (view === "documents") return "Knowledge base";
  if (view === "audit") return "Security and usage";
  return "Generated SQL";
}

function getViewTitle(view: WorkspaceView, activeSessionTitle: string) {
  if (view === "chat") return activeSessionTitle;
  if (view === "sessions") return "Sessions";
  if (view === "data") return "Data Explorer";
  if (view === "documents") return "Documents";
  if (view === "audit") return "Audit Logs";
  if (view === "sql") return "SQL Review";
  return "Dashboard";
}

function readStoredAuth(): StoredAuth | null {
  const raw = localStorage.getItem(authStorageKey);
  if (!raw) return null;

  try {
    const parsed = JSON.parse(raw) as StoredAuth;
    return parsed.access && parsed.refresh && parsed.sessionId ? parsed : null;
  } catch {
    return null;
  }
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function getErrorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Unexpected error.";
}

export default App;
