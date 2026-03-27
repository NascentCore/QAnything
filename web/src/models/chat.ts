import { api_list_knowledge_base } from '@/services';
import { cahtAction, generateUUID, scrollChatBodyToBottom } from '@/utils';
import storage from '@/utils/store';
import { useEffect, useState } from 'react';

const updateFlagKey = 'code_update_2024_12_30';
if (!localStorage.getItem(updateFlagKey)) {
  localStorage.clear();
  localStorage.setItem(updateFlagKey, 'true');
}

export const chat_store_key = 'Chat_Store';
export const chat_store_active_key = 'Chat_Store_Active';
export const chat_store_knowledge_list_select_key = 'Chat_Store_Knowledge_List_Select';

export interface IChatItemMsg {
  content: string;
  role: 'user' | 'assistant';
  id: string;
  date: string;
  source_documents?: any[];
  show_images?: any[];
  raw?: any;
}

export interface IChatItem {
  id: string;
  state: 'success' | 'loading';
  messages: IChatItemMsg[];
}

export interface IChatStore {
  [key: string]: IChatItem;
}

export interface IKnowledgeListItem {
  kb_id: string;
  kb_name: string;
}

const testChatStore: IChatStore = {
  demo: {
    id: 'demo',
    state: 'success',
    messages: [],
  },
};

export default () => {
  // 管理 知识库 数据
  const [knowledgeList, setKnowledgeList] = useState<IKnowledgeListItem[]>([]);
  const [knowledgeListSelect, setKnowledgeListSelect] = useState<string[]>([]);
  const [knowledgeActiveId, setKnowledgeActiveId] = useState();

  // 管理 chat 数据
  const [chatStore, setChatStore] = useState<IChatStore>(testChatStore);
  const [activeChat, setActiveChat] = useState('demo');
  console.log('chatStore', chatStore);
  useEffect(() => {
    const init = async () => {
      const _chatStoreJson: any = await storage.getItem(chat_store_key);
      const _activeChat = localStorage.getItem(chat_store_active_key);
      const _knowledgeListSelect = localStorage.getItem(chat_store_knowledge_list_select_key);
      if (_chatStoreJson) {
        setChatStore(_chatStoreJson);
        setActiveChat(Object.keys(_chatStoreJson)[0]);
      }
      if (_activeChat) {
        setActiveChat(_activeChat);
      }
      if (_knowledgeListSelect) {
        const _knowledgeListSelectJson = JSON.parse(_knowledgeListSelect);
        setKnowledgeListSelect(_knowledgeListSelectJson);
      }
    };
    init();
  }, []);

  useEffect(() => {
    storage.setItem(chat_store_key, chatStore);
  }, [chatStore]);

  useEffect(() => {
    localStorage.setItem(chat_store_active_key, activeChat);
  }, [activeChat]);

  useEffect(() => {
    localStorage.setItem(chat_store_knowledge_list_select_key, JSON.stringify(knowledgeListSelect));
  }, [knowledgeListSelect]);

  useEffect(() => {
    reloadKnowledgeList();
  }, []);

  const reloadKnowledgeList = () => {
    api_list_knowledge_base().then((res: any) => {
      console.log('api_list_knowledge_base', res);
      setKnowledgeList(res?.data || []);
    });
  };

  // 新增聊天数据
  const addChatMsg = (id: string, msg: IChatItemMsg) => {
    setChatStore((chatStore: any) => {
      const _chatStore = JSON.parse(JSON.stringify(chatStore));
      _chatStore[id].messages.push(msg);
      setTimeout(() => {
        scrollChatBodyToBottom(id, true);
      }, 100);
      return _chatStore;
    });
  };

  /**
   * 更新聊天数据
   * @param id chatid
   * @param chatMsgItem
   */
  const updateChatMsg = (id: string, chatMsgItem: IChatItemMsg) => {
    setChatStore((chatStore: any) => {
      const _chatStore = JSON.parse(JSON.stringify(chatStore));
      const chatItem = _chatStore[id];
      const index = chatItem.messages.findIndex((x: any) => x.id === chatMsgItem.id);
      chatItem.messages[index] = chatMsgItem;
      return _chatStore;
    });
    setTimeout(() => {
      scrollChatBodyToBottom(id, true);
    }, 0);
  };

  /**
   * 设置聊天状态
   * @param id
   * @param state
   */
  const setChatItemState = (id: string, state: string) => {
    setChatStore((chatStore: any) => {
      const _chatStore = JSON.parse(JSON.stringify(chatStore));
      _chatStore[id].state = state;
      return _chatStore;
    });
  };

  /**
   * 清空聊天
   */
  const deleteChatStore = (id: string) => {
    setChatStore((chatStore: any) => {
      const _chatStore = JSON.parse(JSON.stringify(chatStore));
      _chatStore[id].messages = [];
      return _chatStore;
    });
  };

  const questionAction = ({ chatid, userMsgValue }: { chatid: string; userMsgValue: string }) => {
    const chatMsgItemUser: IChatItemMsg = {
      content: userMsgValue,
      role: 'user',
      date: '',
      id: generateUUID(),
    };
    addChatMsg(chatid, chatMsgItemUser);
    setChatItemState(chatid, 'loading');
    const msgId = generateUUID();
    const chatMsgItem: IChatItemMsg = {
      content: '正在搜索...',
      role: 'assistant',
      id: msgId,
      date: '',
    };
    addChatMsg(chatid, chatMsgItem);
    cahtAction({
      id: msgId,
      knowledgeListSelect,
      question: userMsgValue,
      onMessage: (chatMsgItem: IChatItemMsg) => {
        updateChatMsg(chatid, chatMsgItem);
      },
      onSuccess: (chatMsgItem: IChatItemMsg) => {
        updateChatMsg(chatid, chatMsgItem);
        setChatItemState(chatid, 'success');
      },
    });
  };

  const reQuestionAction = (chatMsgItem: IChatItemMsg) => {
    console.log('reQuestionAction', chatMsgItem);
    for (const key in chatStore) {
      for (let index = 0; index < chatStore[key].messages.length; index++) {
        const _chatMsgItem = chatStore[key].messages[index];
        if (_chatMsgItem.id === chatMsgItem.id) {
          questionAction({ chatid: key, userMsgValue: chatStore[key].messages[index - 1].content });
          return;
        }
      }
    }
  };

  const addChatWindow = () => {
    setChatStore((chatStore) => {
      console.log('新建对话窗口');
      const id = generateUUID();
      const _chatStore: any = JSON.parse(JSON.stringify(chatStore));
      const chatItem: IChatItem = {
        id,
        state: 'success',
        messages: [],
      };
      _chatStore[id] = chatItem;
      setActiveChat(id);
      return _chatStore;
    });
  };

  const deleteChatWindow = (id: string) => {
    setChatStore((chatStore) => {
      console.log('删除对话窗口', id);
      const _chatStore: any = JSON.parse(JSON.stringify(chatStore));
      if (Object.keys(_chatStore).length === 1) {
        console.log('最后一条对话，不能删除');
        return _chatStore;
      }
      if (activeChat === id) {
        delete _chatStore[id];
        const _id = Object.keys(_chatStore)[0];
        setActiveChat(_id);
      } else {
        delete _chatStore[id];
      }
      return _chatStore;
    });
  };

  const changeChatWindow = (id: string) => {
    setActiveChat(id);
    setTimeout(() => {
      scrollChatBodyToBottom(id, false);
    }, 50);
  };

  return {
    chatStore,
    addChatMsg,
    updateChatMsg,
    deleteChatStore,
    setChatItemState,
    knowledgeList,
    setKnowledgeList,
    knowledgeListSelect,
    setKnowledgeListSelect,
    knowledgeActiveId,
    setKnowledgeActiveId,
    reloadKnowledgeList,
    questionAction,
    reQuestionAction,
    addChatWindow,
    deleteChatWindow,
    changeChatWindow,
    activeChat,
  };
};
