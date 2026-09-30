export interface MessageItem {
  name: string;
  price: string;
}

export interface Message {
  id: string;
  sender: "user" | "assistant";
  text?: string;
  time: string;
  items?: MessageItem[];
  subtotal?: string;
  fees?: string;
  total?: string;
  quickReplies?: string[];
  toolCallPayload?: {
    tool: string;
    params: Record<string, unknown>;
    resultSummary: string;
    latencyMs: number;
  };
}

export interface PresetScenario {
  id: string;
  label: string;
  tag: string;
  prompt: string;
  replyLead: string;
  items: MessageItem[];
  subtotal: string;
  fees: string;
  total: string;
  quickReplies: string[];
  toolTrace: {
    tool: string;
    params: Record<string, unknown>;
    resultSummary: string;
    latencyMs: number;
  };
}

export interface VideoChapter {
  time: string;
  label: string;
}

export interface FaqItem {
  question: string;
  answer: string;
}

export interface PipelineNode {
  id: string;
  stepNumber: string;
  title: string;
  subtitle: string;
  badge: string;
  badgeColor: "emerald" | "blue" | "purple" | "orange" | "zinc";
  metric: string;
  description: string;
  technicalDetails: {
    protocol: string;
    endpointOrFile: string;
    invariants: string[];
    samplePayload: Record<string, unknown>;
  };
}
