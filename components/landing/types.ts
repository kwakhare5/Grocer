export interface MessageItem {
  name: string;
  price: string;
}

export interface VerifiedJourneyTurn {
  turn: number;
  label: string;
  tag: string;
  userInput: string;
  state: string;
  humanState: string;
  latencyMs: number;
  assistantMessage: string;
  items?: MessageItem[];
  subtotal?: string;
  fees?: string;
  total?: string;
  deliveryAddress?: string;
  paymentLink?: string;
  toolTrace: {
    tool: string;
    params: Record<string, unknown>;
    resultSummary: string;
    latencyMs: number;
    invariantTested: string;
  };
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
