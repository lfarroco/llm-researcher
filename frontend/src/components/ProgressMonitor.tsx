import { useState, useEffect } from 'react';
import { createWebSocket } from '../api/client';
import type { WebSocketEvent } from '../types';

interface Props {
	researchId: number;
}

export default function ProgressMonitor({ researchId }: Props) {
	const [events, setEvents] = useState<WebSocketEvent[]>([]);
	const [connected, setConnected] = useState(false);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		let ws: WebSocket | null = null;

		try {
			ws = createWebSocket(researchId);

			ws.onopen = () => {
				setConnected(true);
				setError(null);
			};

			ws.onmessage = (event) => {
				const data: WebSocketEvent = JSON.parse(event.data);
				setEvents((prev) => [...prev, data]);
			};

			ws.onerror = () => {
				setError('WebSocket connection error');
				setConnected(false);
			};

			ws.onclose = () => {
				setConnected(false);
			};
		} catch (err) {
			setError(err instanceof Error ? err.message : 'Failed to connect');
		}

		return () => {
			if (ws) {
				ws.close();
			}
		};
	}, [researchId]);

	const getEventIcon = (type: string) => {
		switch (type) {
			case 'connected': return '🔗';
			case 'status_change': return '📊';
			case 'source_added': return '📄';
			case 'finding_created': return '💡';
			case 'progress': return '⏳';
			case 'error': return '❌';
			case 'completed': return '✅';
			default: return '📌';
		}
	};

	const getEventColor = (type: string) => {
		switch (type) {
			case 'error': return 'text-red-600';
			case 'completed': return 'text-green-600';
			case 'progress': return 'text-blue-600';
			default: return 'text-gray-700';
		}
	};

	return (
		<div className="space-y-3">
			{/* Connection status */}
			<div className="flex items-center gap-2 text-sm">
				<div
					className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-gray-400'
						}`}
				/>
				<span className="text-gray-600">
					{connected ? 'Live updates' : 'Disconnected'}
				</span>
			</div>

			{error && (
				<div className="text-sm text-red-600 bg-red-50 p-2 rounded">
					{error}
				</div>
			)}

			{/* Events timeline */}
			<div className="space-y-2 max-h-96 overflow-y-auto">
				{events.length === 0 ? (
					<p className="text-sm text-gray-500 text-center py-4">
						Waiting for updates...
					</p>
				) : (
					events.map((event, index) => (
						<div
							key={index}
							className="flex gap-3 text-sm p-2 bg-gray-50 rounded"
						>
							<span className="text-lg">{getEventIcon(event.event_type)}</span>
							<div className="flex-1">
								<div className={`font-medium ${getEventColor(event.event_type)}`}>
									{event.event_type.replace(/_/g, ' ')}
								</div>
								{event.data && (
									<div className="text-gray-600 text-xs mt-1">
										{event.event_type === 'status_change' && event.data.status}
										{event.event_type === 'source_added' && event.data.source?.title}
										{event.event_type === 'progress' &&
											`${event.data.percentage?.toFixed(0)}% - ${event.data.message}`}
										{event.event_type === 'error' && event.data.error}
									</div>
								)}
								<div className="text-xs text-gray-400 mt-1">
									{new Date(event.timestamp).toLocaleTimeString()}
								</div>
							</div>
						</div>
					))
				)}
			</div>
		</div>
	);
}
