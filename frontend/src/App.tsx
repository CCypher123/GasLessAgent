import React, { useState, useEffect, useRef } from 'react';
import { Send, User, Bot, RefreshCw, Cpu, Wallet, PenTool, CheckCircle, Shield, ArrowRight } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { v4 as uuidv4 } from 'uuid';
import { ethers } from 'ethers';

const App = () => {
  const [threadId, setThreadId] = useState('');
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [account, setAccount] = useState(null);
  
  // 签名状态管理
  const [signStatus, setSignStatus] = useState('idle'); // idle, signing, submitting, success, error
  const [currentStep, setCurrentStep] = useState(0);

  const messagesEndRef = useRef(null);

  useEffect(() => {
    setThreadId((prev) => prev || uuidv4());
    setMessages([{
      role: 'assistant',
      content: "👋 x402 代付助手 (双签版)\n\n请输入：**给 0x... 转 x USDC**\n我会自动请求 x402 节点，并引导你完成本金和服务费的签名。"
    }]);
    checkWalletConnection();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const checkWalletConnection = async () => {
    if (window.ethereum) {
      try {
        const provider = new ethers.BrowserProvider(window.ethereum);
        const accounts = await provider.listAccounts();
        if (accounts.length > 0) setAccount(accounts[0].address);
      } catch (err) { console.error(err); }
    }
  };

  const connectWallet = async () => {
    if (!window.ethereum) return alert("请安装 MetaMask!");
    try {
      const provider = new ethers.BrowserProvider(window.ethereum);
      const accounts = await provider.send("eth_requestAccounts", []);
      setAccount(accounts[0]);
    } catch (error) { alert("连接失败: " + error.message); }
  };

  // --- 处理批量签名 ---
  const handleBatchSign = async (tasks) => {
    if (!account) return alert("请先连接钱包");
    setSignStatus('signing');
    setCurrentStep(0);

    const results = {};

    try {
      const provider = new ethers.BrowserProvider(window.ethereum);
      const signer = await provider.getSigner();

      // 依次执行所有签名任务
      for (let i = 0; i < tasks.length; i++) {
        setCurrentStep(i + 1); // 更新UI显示当前第几步
        const task = tasks[i];
        
        // 生成随机 nonce (如果在前端生成的话)
        const nonce = ethers.hexlify(ethers.randomBytes(32));
        const message = { ...task.message, nonce }; // 覆盖 nonce 保证唯一

        const signature = await signer.signTypedData(
            task.domain,
            task.types,
            message
        );
        
        // 构造 x402 需要的结构 (v, r, s)
        const sig = ethers.Signature.from(signature);
        
        results[task.id] = {
            from: message.from,
            to: message.to,
            value: message.value,
            validAfter: message.validAfter,
            validBefore: message.validBefore,
            nonce: message.nonce,
            v: sig.v,
            r: sig.r,
            s: sig.s
        };
      }

      // 全部签完，提交给后端
      setSignStatus('submitting');
      await submitSignedPayload(results);

    } catch (error) {
      console.error(error);
      setSignStatus('error');
      alert("签名流程中断: " + error.message);
    }
  };

  const submitSignedPayload = async (signedData) => {
    try {
        // 发送特殊的隐藏消息给后端
        const hiddenMsg = `[System:Signed] ${JSON.stringify(signedData)}`;
        
        // 更新 UI
        setMessages(prev => [...prev, { 
            role: 'user', 
            content: "✅ 签名完成，正在请求 x402 节点上链...",
            isSystem: true 
        }]);

        const response = await fetch('http://localhost:9000/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ thread_id: threadId, message: hiddenMsg })
        });
        
        const data = await response.json();
        setSignStatus('success');
        setMessages(prev => [...prev, { role: 'assistant', content: data.reply }]);

    } catch (e) {
        setSignStatus('error');
        setMessages(prev => [...prev, { role: 'assistant', content: `上链失败: ${e.message}` }]);
    }
  };

  const handleReset = () => {
    setThreadId(uuidv4());
    setMessages([{ role: 'assistant', content: "会话已重置。" }]);
    setSignStatus('idle');
  };

  const handleSend = async () => {
    if (!input.trim()) return;
    const userMsg = input;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setIsLoading(true);
    setSignStatus('idle');

    try {
      // 注意：请确保端口和你 api.py 运行的一致 (9000 或 7890)
      const response = await fetch('http://localhost:9000/chat', { 
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          thread_id: threadId, 
          // 自动带上钱包地址
          message: account ? `[My Wallet Address is ${account}] ${userMsg}` : userMsg 
        })
      });

      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "请求失败");

      const replyContent = data.reply || "";

      // ======================================================
      // 🛠️ 核心修复：超强力 JSON 提取逻辑
      // ======================================================
      
      let batchData = null;
      let cleanContent = replyContent;

      // 1. 尝试匹配 Markdown 代码块 (```json ... ```)
      // 正则解释：
      // ```json\s*  -> 匹配 ```json 开头，允许后面有空格或换行
      // ([\s\S]*?)   -> 懒惰匹配中间的所有字符（包括换行符）
      // \s*```       -> 匹配结尾的 ```，允许前面有空格或换行
      const codeBlockRegex = /```json\s*([\s\S]*?)\s*```/;
      const match = replyContent.match(codeBlockRegex);

      if (match) {
        try {
            // match[1] 是纯 JSON 字符串
            const parsed = JSON.parse(match[1]);
            
            // 只有当 action 是 batch_sign_auth 时才认为是交易数据
            if (parsed.action === 'batch_sign_auth') {
                batchData = parsed.tasks;
                // ✂️ 从显示的文本中把这块 JSON 彻底删掉
                cleanContent = replyContent.replace(match[0], "").trim(); 
            }
        } catch (e) {
            console.error("JSON 解析失败:", e);
        }
      } 
      // 2. 如果后端没发 Markdown 格式，尝试直接暴力找 JSON 对象 {...}
      // (作为备份方案)
      else if (replyContent.includes('"action": "batch_sign_auth"')) {
         try {
             // 找到第一个 { 和最后一个 }
             const start = replyContent.indexOf('{');
             const end = replyContent.lastIndexOf('}');
             if (start !== -1 && end !== -1) {
                 const jsonStr = replyContent.substring(start, end + 1);
                 const parsed = JSON.parse(jsonStr);
                 if (parsed.action === 'batch_sign_auth') {
                     batchData = parsed.tasks;
                     // ✂️ 删掉 JSON
                     cleanContent = replyContent.substring(0, start).trim();
                 }
             }
         } catch(e) {}
      }

      // 3. 更新 UI
      if (batchData) {
          // 有交易数据：显示文本 + 按钮卡片
          setMessages(prev => [...prev, { 
              role: 'assistant', 
              content: cleanContent, // 这里只剩下纯文本描述，JSON 已被移除
              batchData: batchData 
          }]);
      } else {
          // 普通回复
          setMessages(prev => [...prev, { role: 'assistant', content: cleanContent }]);
      }

    } catch (error) {
      setMessages(prev => [...prev, { role: 'assistant', content: `❌ Error: ${error.message}` }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-screen bg-slate-900 text-slate-100 font-sans">
      <div className="w-64 bg-slate-800 border-r border-slate-700 hidden md:flex flex-col p-4">
        <div className="flex items-center gap-2 mb-8 text-blue-400">
          <Cpu size={28} />
          <h1 className="text-xl font-bold">x402 Client</h1>
        </div>
        <div className="mb-6 p-3 bg-slate-900 rounded-xl border border-slate-700">
            <div className="text-xs text-slate-500 mb-2 font-bold">ACCOUNT</div>
            {account ? (
                <div className="text-emerald-400 text-xs font-mono break-all">{account}</div>
            ) : (
                <button onClick={connectWallet} className="w-full py-2 bg-blue-600 rounded text-xs">Connect Wallet</button>
            )}
        </div>
        <div className="flex-1"/>
        <button onClick={handleReset} className="w-full py-2 bg-slate-700 rounded text-sm flex justify-center gap-2"><RefreshCw size={14}/> Reset</button>
      </div>

      <div className="flex-1 flex flex-col relative max-w-4xl mx-auto w-full">
        <div className="md:hidden p-4 bg-slate-800 flex justify-between"><span className="font-bold">x402</span><Wallet onClick={connectWallet}/></div>

        <div className="flex-1 overflow-y-auto p-4 space-y-6 custom-scrollbar">
          {messages.map((msg, idx) => (
            <div key={idx} className={`flex gap-4 ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
              {!msg.isSystem && <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${msg.role === 'assistant' ? 'bg-blue-600' : 'bg-emerald-600'}`}>{msg.role === 'assistant' ? <Bot size={20}/> : <User size={20}/>}</div>}
              
              <div className="max-w-[85%] space-y-3">
                  {msg.content && (
                    <div className={`px-5 py-3 rounded-2xl shadow-md ${msg.role === 'assistant' ? 'bg-slate-800 border border-slate-700' : msg.isSystem ? 'bg-transparent text-slate-500 text-xs' : 'bg-blue-600'}`}>
                         {!msg.isSystem ? <div className="markdown-body text-sm"><ReactMarkdown>{msg.content}</ReactMarkdown></div> : msg.content}
                    </div>
                  )}

                  {/* 签名任务卡片 */}
                  {msg.batchData && (
                      <div className="bg-slate-900 border border-blue-500/40 rounded-xl p-5 shadow-xl w-full max-w-sm">
                          <div className="flex items-center gap-2 text-blue-400 mb-4 border-b border-slate-700 pb-2">
                              <Shield size={20} />
                              <span className="font-bold">需要签名 (共 {msg.batchData.length} 笔)</span>
                          </div>
                          
                          <div className="space-y-3 mb-6">
                              {msg.batchData.map((task, i) => (
                                  <div key={i} className={`flex items-center gap-3 p-3 rounded-lg border ${currentStep > i ? 'bg-emerald-900/30 border-emerald-500/30 text-emerald-400' : 'bg-slate-800 border-slate-700 text-slate-400'}`}>
                                      {currentStep > i ? <CheckCircle size={18}/> : <div className="w-4 h-4 rounded-full border-2 border-slate-500 flex items-center justify-center text-[10px]">{i+1}</div>}
                                      <div className="text-xs font-mono">{task.label}</div>
                                  </div>
                              ))}
                          </div>

                          {signStatus === 'signing' ? (
                             <button disabled className="w-full py-3 bg-slate-700 rounded-lg text-slate-300 flex justify-center gap-2">
                                <RefreshCw className="animate-spin" size={18}/> 请在钱包中签名 ({currentStep}/{msg.batchData.length})...
                             </button>
                          ) : signStatus === 'submitting' ? (
                             <button disabled className="w-full py-3 bg-slate-700 rounded-lg text-slate-300 flex justify-center gap-2">
                                <RefreshCw className="animate-spin" size={18}/> 提交上链中...
                             </button>
                          ) : signStatus === 'success' ? (
                             <button disabled className="w-full py-3 bg-emerald-900/50 text-emerald-400 border border-emerald-500 rounded-lg flex justify-center gap-2">
                                <CheckCircle size={18}/> 全部完成
                             </button>
                          ) : (
                             <button onClick={() => handleBatchSign(msg.batchData)} className="w-full py-3 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-lg flex justify-center gap-2 transition hover:scale-[1.02]">
                                <PenTool size={18}/> 开始签名
                             </button>
                          )}
                      </div>
                  )}
              </div>
            </div>
          ))}
          {isLoading && <div className="ml-14 text-slate-500 text-xs animate-pulse">正在询问 x402 节点...</div>}
          <div ref={messagesEndRef} />
        </div>

        <div className="p-4 bg-slate-900 border-t border-slate-800">
            <div className="max-w-3xl mx-auto relative flex items-center">
                <input type="text" value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && handleSend()} placeholder="输入指令..." className="w-full bg-slate-800 border-2 border-slate-700 text-slate-100 rounded-xl py-3 pl-4 pr-12 focus:border-blue-500 transition-all placeholder-slate-500" disabled={isLoading} />
                <button onClick={handleSend} disabled={isLoading} className="absolute right-2 p-2 bg-blue-600 text-white rounded-lg"><Send size={18} /></button>
            </div>
        </div>
      </div>
    </div>
  );
};

export default App;