import { create } from 'zustand';

/* ── Karşılaştırma (pin) store'u ─────────────────────────────────────────────
   Stüdyo modunda iki analizi yan yana görebilmek için aktif mesajın sonucu
   buraya "pinned" olarak saklanır. Basit module-level zustand store; App-level
   BI store'a dokunmaz. */

export interface PinnedResult {
  messageId: string;
  title: string;
  data?: {
    columns: string[];
    rows: any[][];
    row_count?: number;
  };
  visualization?: any;
}

interface CompareState {
  pinned: PinnedResult | null;
  pinResult: (result: PinnedResult) => void;
  clearPinned: () => void;
}

export const useCompareStore = create<CompareState>((set) => ({
  pinned: null,
  pinResult: (result) => set({ pinned: result }),
  clearPinned: () => set({ pinned: null }),
}));
