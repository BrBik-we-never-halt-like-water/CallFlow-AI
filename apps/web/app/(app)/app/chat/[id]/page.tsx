'use client';

import { useParams } from 'next/navigation';
import { ChatShell } from '../chat-shell';

export default function ChatConversationPage() {
  const params = useParams<{ id: string }>();
  const channelId = typeof params?.id === 'string' ? params.id : null;
  return <ChatShell channelId={channelId} />;
}
