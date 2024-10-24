import { IChatItemMsg } from '@/models/chat';

export function generateUUID(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export function scrollChatBodyToBottom() {
  document.querySelector('.chat-container')?.scrollTo({
    top: 9999999999,
    behavior: 'smooth',
  });
}

export const getChatResponseJsonFromResponseText = (responseText: string) => {
  let json: any = {};
  const lines = responseText.split('\n');
  for (const line of lines) {
    if (line.startsWith('data: ')) {
      try {
        const data = JSON.parse(line.slice(6));
        if (data.msg === 'success stream chat') {
          json = data;
          break;
        }
      } catch (e) {
        console.error('解析JSON时出错:', e);
      }
    }
  }
  const { response, source_documents } = json;
  const msgId = generateUUID();
  const chatMsgItem: IChatItemMsg = {
    content: response,
    source_documents,
    role: 'assistant',
    id: msgId,
    date: '',
    raw: json,
  };
  return chatMsgItem;
};

export const cahtAction = async ({
  id,
  knowledgeListSelect,
  question,
  onMessage,
  onSuccess,
}: {
  id: string; // msgid
  question: string;
  knowledgeListSelect: string[];
  onMessage: (chatMsgItem: IChatItemMsg) => void;
  onSuccess: (chatMsgItem: IChatItemMsg) => void;
}) => {
  const response = await fetch(
    'http://knowledge.llm.sxwl.ai:30002/api/local_doc_qa/local_doc_chat',
    {
      method: 'POST',
      headers: {
        Accept: 'text/event-stream,application/json, text/event-stream',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7,mt;q=0.6,pl;q=0.5',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_id: 'zzp',
        kb_ids: knowledgeListSelect,
        history: [],
        question: question,
        streaming: true,
        networking: false,
        product_source: 'saas',
        rerank: false,
        only_need_search_results: false,
        hybrid_search: true,
        max_token: 1024,
        api_base: '',
        api_key: '',
        model: '',
        api_context_length: 8192,
        chunk_size: 800,
        top_p: 1,
        top_k: 30,
        temperature: 0.5,
      }),
    },
  );

  const reader = (response as any).body.getReader();
  const decoder = new TextDecoder();
  let fullChunk = '';
  let fullResponse = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const chunk = decoder.decode(value);
    fullChunk += chunk;
    const lines = chunk.split('\n');
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const data = JSON.parse(line.slice(6));
          if (data.response) {
            fullResponse += data.response;
            console.log('fullResponse', fullResponse);
            const chatMsgItem: IChatItemMsg = {
              content: fullResponse,
              role: 'assistant',
              id: id,
              date: '',
            };
            onMessage(chatMsgItem);
          }
        } catch (e) {
          console.error('解析JSON时出错:', e);
        }
      }
    }
  }
  const chatMsgItem2: IChatItemMsg = getChatResponseJsonFromResponseText(fullChunk);
  onSuccess({ ...chatMsgItem2, id: id });
};