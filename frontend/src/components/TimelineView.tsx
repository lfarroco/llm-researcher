interface TimelineEvent {
	id: string;
	label: string;
	time: string;
	detail?: string;
	type: 'research' | 'source' | 'finding';
}

interface Props {
	events: TimelineEvent[];
}

const colorByType: Record<TimelineEvent['type'], string> = {
	research: 'bg-blue-500',
	source: 'bg-green-500',
	finding: 'bg-indigo-500',
};

export default function TimelineView({ events }: Props) {
	if (events.length === 0) {
		return (
			<div className="border border-dashed border-gray-300 rounded-lg p-6 text-center">
				<p className="text-sm text-gray-500">No timeline events yet.</p>
			</div>
		);
	}

	return (
		<div>
			<h3 className="text-sm font-semibold text-gray-700 mb-3">Recent Activity</h3>
			<div className="space-y-3">
				{events.map((event) => (
					<div key={event.id} className="flex gap-3">
						<div className="pt-1">
							<span className={`block w-2.5 h-2.5 rounded-full ${colorByType[event.type]}`} />
						</div>
						<div className="flex-1 border border-gray-200 rounded-lg p-3">
							<div className="flex items-center justify-between gap-2">
								<p className="text-sm font-medium text-gray-900">{event.label}</p>
								<p className="text-xs text-gray-500">{new Date(event.time).toLocaleString()}</p>
							</div>
							{event.detail && <p className="mt-1 text-xs text-gray-600">{event.detail}</p>}
						</div>
					</div>
				))}
			</div>
		</div>
	);
}
