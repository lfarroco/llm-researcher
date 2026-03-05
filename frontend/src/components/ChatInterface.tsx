import { useState, useEffect, useRef } from 'react';
import { api } from '../api/client';
import type { ChatMessage } from '../types';

interface Props {
	researchId: number;
}

export default function ChatInterface({ researchId }: Props) {
	const [messages, setMessages] = useState<ChatMessage[]>([]);
	const [input, setInput] = useState('');
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const messagesEndRef = useRef<HTMLDivElement>(null);

	useEffect(() => {
		loadChatHistory();
	}, [researchId]);

	useEffect(() => {
		messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
	}, [messages]);

	const loadChatHistory = async () => {
		try {
			const history = await api.getChatHistory(researchId);
			setMessages(history);
		} catch (err) {
			console.error('Failed to load chat history:', err);
		}
	};

	const handleSend = async (e: React.FormEvent) => {
		e.preventDefault();
		if (!input.trim() || loading) return;

		const userMessage = input;
		setInput('');
		setLoading(true);
		setError(null);

		try {
			await api.sendChatMessage(researchId, userMessage);
			await loadChatHistory(); // Reload to get both user and assistant messages
		} catch (err) {
			setError(err instanceof Error ? err.message : 'Failed to send message');
		} finally {
			setLoading(false);
		}
	};

	return (
		<div className="flex flex-col h-[500px]">
			{/* Messages */}
			<div className="flex-1 overflow-y-auto space-y-4 p-4 bg-gray-50 rounded-t-lg">
				{messages.length === 0 ? (
					<div className="text-center text-gray-500 py-8">
						<p>No messages yet</p>
						<p className="text-sm mt-2">Ask questions about the research findings</p>
					</div>
				) : (
					messages.map((message) => (
						<div
							key={message.id}
							className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'
								}`}
						>
							<div
								className={`max-w-[80%] rounded-lg px-4 py-2 ${message.role === 'user'
										? 'bg-blue-600 text-white'
										: 'bg-white text-gray-900 border'
									}`}
							>
								<p className="text-sm whitespace-pre-wrap">{message.content}</p>
								<p
									className={`text-xs mt-1 ${message.role === 'user' ? 'text-blue-100' : 'text-gray-500'
										}`}
								>
									{new Date(message.created_at).toLocaleTimeString()}
								</p>
							</div>
						</div>
					))
				)}

				{loading && (
					<div className="flex justify-start">
						<div className="bg-white border rounded-lg px-4 py-2">
							<p className="text-sm text-gray-500">Thinking...</p>
						</div>
					</div>
				)}

				<div ref={messagesEndRef} />
			</div>

			{/* Input form */}
			<form onSubmit={handleSend} className="border-t bg-white p-4 rounded-b-lg">
				{error && (
					<div className="text-sm text-red-600 mb-2">
						{error}
					</div>
				)}
				<div className="flex gap-2">
					<input
						type="text"
						value={input}
						onChange={(e) => setInput(e.target.value)}
						placeholder="Ask a question about the research..."
						className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
						disabled={loading}
					/>
					<button
						type="submit"
						disabled={loading || !input.trim()}
						className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
					>
						Send
					</button>
				</div>
			</form>
		</div>
	);
}
