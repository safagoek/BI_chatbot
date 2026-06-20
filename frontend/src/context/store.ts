import { create } from 'zustand';

export interface FileSource {
  id: string;
  alias: string;
  original_name: string;
  file_path: string;
  row_count: number;
  schema: Record<string, string>;
  uploaded_at: string;
}

export interface DBSource {
  id: string;
  type: string;
  display_name: string;
  connection_details: Record<string, any>;
  schema: Record<string, any>;
  last_schema_update: string;
  labels: string[];
  is_active: boolean;
}

export interface Message {
  id: string;
  role: 'user' | 'agent';
  text?: string;
  statusHistory: string[];
  code?: string;
  codeLanguage?: 'python' | 'sql';
  data?: {
    columns: string[];
    rows: any[][];
    row_count: number;
    value?: any;
  };
  visualization?: any;
  error?: string;
  auto_corrections?: any;
}

export interface ChatSession {
  id: string;
  title: string;
  activeSourceId: string;
  chatHistory: Message[];
  created_at: string;
  selectedSourceIds?: string[];
  joinRelations?: JoinRelation[];
}

export interface JoinRelation {
  leftSourceId: string;
  leftColumn: string;
  rightSourceId: string;
  rightColumn: string;
  joinType: 'auto' | 'inner' | 'left' | 'right' | 'full';
}

interface BIStore {
  activeTab: 'chat' | 'files' | 'sources';
  sources: DBSource[];
  files: FileSource[];
  activeSourceId: string;
  sessions: ChatSession[];
  activeSessionId: string;
  chatHistory: Message[];
  isThinking: boolean;
  selectedSourceIds: string[];
  joinRelations: JoinRelation[];
  apiConfig: {
    apiKey: string;
    baseUrl: string;
    model: string;
  };
  showSourcePicker: boolean;
  sourcePickerMode: 'edit' | 'create';
  
  language: 'tr' | 'en';
  setLanguage: (lang: 'tr' | 'en') => void;

  activeMessageId: string | null;
  messageSelectionCount: number;
  setActiveMessageId: (id: string | null) => void;

  visualizerDismissed: boolean;
  setVisualizerDismissed: (dismissed: boolean) => void;


  // Actions
  setActiveTab: (tab: 'chat' | 'files' | 'sources') => void;
  setApiConfig: (config: { apiKey: string; baseUrl: string; model: string }) => void;
  fetchApiConfig: () => Promise<void>;
  setActiveSourceId: (id: string) => Promise<void>;

  fetchSources: () => Promise<void>;
  fetchFiles: () => Promise<void>;
  deleteFile: (id: string) => Promise<void>;
  addDBSource: (db: Omit<DBSource, 'last_schema_update'>) => Promise<void>;
  
  // Session Actions
  fetchSessions: () => Promise<void>;
  createSession: (title?: string) => Promise<void>;
  selectSession: (id: string) => Promise<void>;
  deleteSession: (id: string) => Promise<void>;
  renameSession: (id: string, title: string) => Promise<void>;
  setSelectedSourceIds: (ids: string[]) => void;
  setJoinRelations: (relations: JoinRelation[]) => void;
  setShowSourcePicker: (show: boolean, mode?: 'edit' | 'create') => void;
  
  sendMessage: (text: string) => void;
  clearChat: () => Promise<void>;
  updateMessageCode: (messageId: string, code: string, data: any, visualization: any, text: string, error?: string, auto_corrections?: any) => void;
}

export const BACKEND_BASE = (typeof window !== 'undefined') ? `${window.location.protocol}//${window.location.hostname}:8000` : 'http://127.0.0.1:8000';
const BACKEND_URL = BACKEND_BASE.replace(/^https?:\/\//, '');

const WELCOME_MSG: Message = {
  id: 'welcome',
  role: 'agent',
  text: '### DeepBI Analytics Studio & Karar Destek Sistemi\n\nVeri analitiği ve iş zekası stüdyosuna hoş geldiniz. Bu çalışma alanında seçili veri kümeleriniz üzerinde gelişmiş analitik sorgular (SQL/Pandas) çalıştırabilir, makine öğrenmesi algoritmalarıyla ileriye dönük tahminlemeler yapabilir ve dinamik Plotly grafik raporları oluşturabilirsiniz.\n\n- **Analiz Koşmak İçin:** Alt kısımdaki analiz talep panelini kullanın.\n- **Veri Kaynakları İçin:** Sol panel altındaki *Veri Kaynakları* sekmesini açın.\n- **Bağlantı Ayarları:** Sol panel altındaki *Ayarlar* bölümünü ziyaret edin.',
  statusHistory: []
};

// Only persist lightweight user preferences (NOT session data — that lives in DB)
const getApiConfig = () => ({
  apiKey: localStorage.getItem('deepseek_key') || '',
  baseUrl: localStorage.getItem('deepseek_url') || 'https://api.deepseek.com/v1',
  model: localStorage.getItem('deepseek_model') || 'deepseek-coder'
});

const normalizeMessages = (msgs: any[]): Message[] =>
  msgs.map((m: any) => ({
    ...m,
    statusHistory: Array.isArray(m.statusHistory) ? m.statusHistory : [],
    data: m.data ?? undefined,
    visualization: m.visualization ?? undefined,
    error: m.error ?? undefined,
  }));

export const useBIStore = create<BIStore>((set, get) => ({
  activeTab: 'chat',
  sources: [],
  files: [],
  sessions: [],
  activeSessionId: '',
  language: (typeof window !== 'undefined' ? localStorage.getItem('language') as 'tr' | 'en' : 'tr') || 'tr',
  setLanguage: (lang) => {
    localStorage.setItem('language', lang);
    set({ language: lang });
  },

  activeMessageId: null,
  messageSelectionCount: 0,
  setActiveMessageId: (id) => set((state) => ({ activeMessageId: id, messageSelectionCount: state.messageSelectionCount + 1, visualizerDismissed: false })),

  visualizerDismissed: false,
  setVisualizerDismissed: (dismissed) => set({ visualizerDismissed: dismissed }),


  activeSourceId: '',
  chatHistory: [WELCOME_MSG],
  isThinking: false,
  selectedSourceIds: [],
  joinRelations: [],
  apiConfig: getApiConfig(),
  showSourcePicker: false,
  sourcePickerMode: 'edit',

  setActiveTab: (tab) => set({ activeTab: tab }),
  
  setApiConfig: (config) => {
    fetch(`${BACKEND_BASE}/api/settings`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config)
    }).catch(err => console.error("Save settings to DB error", err));

    localStorage.setItem('deepseek_key', config.apiKey);
    localStorage.setItem('deepseek_url', config.baseUrl);
    localStorage.setItem('deepseek_model', config.model);
    set({ apiConfig: config });
  },

  fetchApiConfig: async () => {
    try {
      const res = await fetch(`${BACKEND_BASE}/api/settings`);
      if (res.ok) {
        const config = await res.json();
        set({ apiConfig: config });
      }
    } catch (e) {
      console.error("Fetch API config error", e);
    }
  },


  setActiveSourceId: async (id) => {
    const activeSessionId = get().activeSessionId;
    try {
      if (activeSessionId) {
        await fetch(`${BACKEND_BASE}/api/sessions/${activeSessionId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ active_source_id: id })
        });
      }
    } catch (e) {
      console.error("Set active source id error", e);
    }
    set((state) => {
      const updatedSessions = state.sessions.map(s => {
        if (s.id === activeSessionId) return { ...s, activeSourceId: id, selectedSourceIds: [id] };
        return s;
      });
      return { activeSourceId: id, selectedSourceIds: [id], sessions: updatedSessions };
    });
  },

  fetchSources: async () => {
    try {
      const res = await fetch(`${BACKEND_BASE}/api/sources`);
      if (res.ok) set({ sources: await res.json() });
    } catch (e) {
      console.error("Sources fetch error", e);
    }
  },

  fetchFiles: async () => {
    try {
      const res = await fetch(`${BACKEND_BASE}/api/files`);
      if (res.ok) set({ files: await res.json() });
    } catch (e) {
      console.error("Files fetch error", e);
    }
  },

  deleteFile: async (id) => {
    try {
      const res = await fetch(`${BACKEND_BASE}/api/files/${id}`, { method: 'DELETE' });
      if (res.ok) {
        await get().fetchFiles();
        if (get().activeSourceId === id) get().setActiveSourceId(get().sources[0]?.id || get().files[0]?.id || '');
        // Remove from multi-source selection if it was selected
        set((state) => ({
          selectedSourceIds: state.selectedSourceIds.filter(sid => sid !== id)
        }));
      }
    } catch (e) {
      console.error("File delete error", e);
    }
  },

  addDBSource: async (db) => {
    try {
      const res = await fetch(`${BACKEND_BASE}/api/sources`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(db)
      });
      if (res.ok) await get().fetchSources();
    } catch (e) {
      console.error("DB Add error", e);
    }
  },

  // ─── Session Actions (fully DB-backed) ────────────────────────────────────

  fetchSessions: async () => {
    await get().fetchApiConfig(); // Sync API config on mount
    try {
      const res = await fetch(`${BACKEND_BASE}/api/sessions`);

      if (!res.ok) return;

      const backendSessions = await res.json();

      // If no sessions exist in DB → create a default one
      if (backendSessions.length === 0) {
        await get().createSession('Varsayılan Sohbet');
        return;
      }

      const mappedSessions: ChatSession[] = backendSessions.map((s: any) => ({
        id: s.id,
        title: s.title,
        activeSourceId: s.active_source_id,
        created_at: s.created_at,
        chatHistory: [], // will be loaded by selectSession
        selectedSourceIds: s.selected_sources ? JSON.parse(s.selected_sources) : [],
        joinRelations: s.relationships ? JSON.parse(s.relationships) : []
      }));

      set({ sessions: mappedSessions });

      // Restore last active session (from lightweight localStorage pref)
      const savedActiveId = localStorage.getItem('deepbi_active_session_id');
      const targetId = (savedActiveId && mappedSessions.some(s => s.id === savedActiveId))
        ? savedActiveId
        : mappedSessions[0].id;

      await get().selectSession(targetId);
    } catch (e) {
      console.error("Sessions fetch error", e);
    }
  },

  createSession: async (title) => {
    try {
      const activeSrc = get().activeSourceId || get().sources[0]?.id || get().files[0]?.id || '';
      const res = await fetch(`${BACKEND_BASE}/api/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: title || 'Yeni Sohbet', active_source_id: activeSrc })
      });
      if (res.ok) {
        const newS = await res.json();
        const newSession: ChatSession = {
          id: newS.id,
          title: newS.title,
          activeSourceId: newS.active_source_id,
          created_at: newS.created_at,
          chatHistory: [WELCOME_MSG]
        };
        set((state) => ({
          sessions: [newSession, ...state.sessions],
          activeSessionId: newSession.id,
          chatHistory: newSession.chatHistory,
          activeSourceId: newSession.activeSourceId,
          selectedSourceIds: [],
          joinRelations: [],
          activeTab: 'chat',
          isThinking: false,
          activeMessageId: null,
          visualizerDismissed: false,
        }));

        localStorage.setItem('deepbi_active_session_id', newSession.id);
      }
    } catch (e) {
      console.error("Create session error", e);
    }
  },

  selectSession: async (id) => {
    try {
      const [msgRes, sessionRes] = await Promise.all([
        fetch(`${BACKEND_BASE}/api/sessions/${id}/messages`),
        fetch(`${BACKEND_BASE}/api/sessions/${id}`)
      ]);

      if (msgRes.ok && sessionRes.ok) {
        const messages = await msgRes.json();
        const sessionMeta = await sessionRes.json();

        const normalized = normalizeMessages(messages);
        const history = normalized.length > 0 ? normalized : [WELCOME_MSG];

        const selectedSources = sessionMeta.selected_sources ? JSON.parse(sessionMeta.selected_sources) : [];
        const relationships = sessionMeta.relationships ? JSON.parse(sessionMeta.relationships) : [];

        set((state) => {
          const updatedSessions = state.sessions.map(s =>
            s.id === id ? { ...s, chatHistory: history, activeSourceId: sessionMeta.active_source_id, selectedSourceIds: selectedSources, joinRelations: relationships } : s
          );
          return {
            activeSessionId: id,
            chatHistory: history,
            activeSourceId: sessionMeta.active_source_id,
            selectedSourceIds: selectedSources,
            joinRelations: relationships,
            sessions: updatedSessions,
            isThinking: false,
            activeMessageId: null,
            visualizerDismissed: false,
          };
        });

        localStorage.setItem('deepbi_active_session_id', id);
      }
    } catch (e) {
      console.error("Select session error", e);
    }
  },

  deleteSession: async (id) => {
    try {
      const res = await fetch(`${BACKEND_BASE}/api/sessions/${id}`, { method: 'DELETE' });
      if (res.ok) {
        set((state) => {
          const updated = state.sessions.filter(s => s.id !== id);
          if (updated.length === 0) {
            // No sessions left — create fresh one async
            setTimeout(() => get().createSession('Varsayılan Sohbet'), 50);
            return { sessions: [], chatHistory: [WELCOME_MSG], activeSessionId: '' };
          }
          const nextId = state.activeSessionId === id ? updated[0].id : state.activeSessionId;
          setTimeout(() => get().selectSession(nextId), 50);
          return { sessions: updated, activeSessionId: nextId };
        });
      }
    } catch (e) {
      console.error("Delete session error", e);
    }
  },

  renameSession: async (id, title) => {
    try {
      const res = await fetch(`${BACKEND_BASE}/api/sessions/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title })
      });
      if (res.ok) {
        set((state) => ({
          sessions: state.sessions.map(s => s.id === id ? { ...s, title } : s)
        }));
      }
    } catch (e) {
      console.error("Rename session error", e);
    }
  },

  setSelectedSourceIds: (ids) => {
    const activeSessionId = get().activeSessionId;
    if (activeSessionId) {
      fetch(`${BACKEND_BASE}/api/sessions/${activeSessionId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ selected_sources: ids })
      }).catch(err => console.error("Save selected sources error", err));
    }
    set((state) => {
      const updatedSessions = state.sessions.map(s => {
        if (s.id === activeSessionId) return { ...s, selectedSourceIds: ids };
        return s;
      });
      return { selectedSourceIds: ids, sessions: updatedSessions };
    });
  },

  setJoinRelations: (relations) => {
    const activeSessionId = get().activeSessionId;
    if (activeSessionId) {
      fetch(`${BACKEND_BASE}/api/sessions/${activeSessionId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ relationships: relations })
      }).catch(err => console.error("Save join relations error", err));
    }
    set((state) => {
      const updatedSessions = state.sessions.map(s => {
        if (s.id === activeSessionId) return { ...s, joinRelations: relations };
        return s;
      });
      return { joinRelations: relations, sessions: updatedSessions };
    });
  },
  setShowSourcePicker: (show, mode = 'edit') => set({ showSourcePicker: show, sourcePickerMode: mode }),

  // ─── Messaging ─────────────────────────────────────────────────────────────

  sendMessage: (text) => {
    const userMsgId = `user-${Date.now()}`;
    const agentMsgId = `agent-${Date.now()}`;

    const userMsg: Message = { id: userMsgId, role: 'user', text, statusHistory: [] };
    const agentMsg: Message = { id: agentMsgId, role: 'agent', statusHistory: ['Bağlantı kuruluyor...'] };

    const isFirstUserMessage = get().chatHistory.filter(m => m.role === 'user').length === 0;
    const updatedTitle = isFirstUserMessage
      ? text.trim().substring(0, 28) + (text.trim().length > 28 ? '...' : '')
      : undefined;

    const currentChatHistory = [...get().chatHistory, userMsg, agentMsg];

    // Update in-memory state (no localStorage write for session data)
    set((state) => {
      const updatedSessions = state.sessions.map(s =>
        s.id === state.activeSessionId
          ? { ...s, chatHistory: currentChatHistory, title: updatedTitle || s.title }
          : s
      );
      return { chatHistory: currentChatHistory, sessions: updatedSessions, isThinking: true, activeMessageId: null, visualizerDismissed: false };
    });


    // Update session title in DB if first message
    if (isFirstUserMessage && updatedTitle) {
      fetch(`${BACKEND_BASE}/api/sessions/${get().activeSessionId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: updatedTitle })
      }).catch(err => console.error("Update session title error", err));
    }

    // Connect WebSocket
    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const socket = new WebSocket(`${wsProtocol}//${BACKEND_URL}/ws/chat`);
    // Guard: prevents onclose from double-resetting isThinking after a clean done/error
    let isDone = false;

    socket.onopen = () => {
      socket.send(JSON.stringify({
        text,
        source_id: get().activeSourceId,
        source_ids: get().selectedSourceIds,
        relationships: get().joinRelations,
        session_id: get().activeSessionId,
        api_key: get().apiConfig.apiKey,
        base_url: get().apiConfig.baseUrl,
        model: get().apiConfig.model,
        user_msg_id: userMsgId,
        agent_msg_id: agentMsgId
      }));
    };

    socket.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      // Mark terminal states before set() so the onclose guard activates immediately
      if (msg.type === "done" || msg.type === "error") isDone = true;
      set((state) => {
        const history = [...state.chatHistory];
        const idx = history.findIndex(m => m.id === agentMsgId);
        if (idx === -1) return {};

        const m = { ...history[idx] };
        let shouldStopThinking = false;

        if (msg.type === "status") {
          m.statusHistory = [...m.statusHistory, msg.message];
        } else if (msg.type === "code") {
          m.code = msg.code;
          m.codeLanguage = msg.language;
        } else if (msg.type === "result") {
          m.data = msg.data;
          m.visualization = msg.visualization;
          if (msg.auto_corrections) m.auto_corrections = msg.auto_corrections;
        } else if (msg.type === "error") {
          m.error = msg.message;
          m.text = `İşlem sırasında bir hata oluştu: ${msg.message}`;
          shouldStopThinking = true;
          try { socket.close(); } catch (e) {}
        } else if (msg.type === "done") {
          m.text = msg.final_response;
          shouldStopThinking = true;
          try { socket.close(); } catch (e) {}
        }
        history[idx] = m;

        // Keep in-memory session cache up to date (no localStorage write)
        const updatedSessions = state.sessions.map(s =>
          s.id === state.activeSessionId ? { ...s, chatHistory: history } : s
        );
        return { 
          chatHistory: history, 
          sessions: updatedSessions,
          isThinking: shouldStopThinking ? false : state.isThinking
        };
      });
    };

    socket.onerror = () => {
      isDone = true; // prevent onclose from firing an additional reset
      set((state) => {
        const history = [...state.chatHistory];
        const idx = history.findIndex(m => m.id === agentMsgId);
        if (idx !== -1) {
          history[idx] = {
            ...history[idx],
            text: "WebSocket sunucu bağlantısı başarısız oldu. Sunucunun çalıştığından emin olun."
          };
        }
        return { chatHistory: history, isThinking: false };
      });
    };

    // Only reset isThinking if a proper done/error signal was NOT received
    socket.onclose = () => { if (!isDone) set({ isThinking: false }); };
  },

  clearChat: async () => {
    const activeSessionId = get().activeSessionId;
    try {
      if (activeSessionId) {
        await fetch(`${BACKEND_BASE}/api/sessions/${activeSessionId}/clear`, { method: 'POST' });
      }
    } catch (e) {
      console.error("Clear chat error", e);
    }
    const clearedHistory: Message[] = [{
      id: 'welcome',
      role: 'agent',
      text: 'Konuşma geçmişi temizlendi. Verileriniz hakkında yeni bir soru sorabilirsiniz!',
      statusHistory: []
    }];
    set((state) => ({
      chatHistory: clearedHistory,
      sessions: state.sessions.map(s =>
        s.id === activeSessionId ? { ...s, chatHistory: clearedHistory } : s
      ),
      activeMessageId: null,
      visualizerDismissed: false,
    }));

  },

  updateMessageCode: (messageId, code, data, visualization, text, error, auto_corrections) => {
    set((state) => {
      const history = state.chatHistory.map(m => {
        if (m.id === messageId) {
          return { ...m, code, data: error ? undefined : data, visualization: error ? undefined : visualization, text, error, auto_corrections: auto_corrections ?? m.auto_corrections };
        }
        return m;
      });
      return {
        chatHistory: history,
        sessions: state.sessions.map(s =>
          s.id === state.activeSessionId ? { ...s, chatHistory: history } : s
        ),
        visualizerDismissed: false
      };
    });
  }
}));

export type { BIStore };
