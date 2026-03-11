interface Props {
	status: string;
	sourceCount: number;
	findingCount: number;
	subQueryCount: number;
	completedSubQueryCount: number;
}

export default function MetricsCards({
	status,
	sourceCount,
	findingCount,
	subQueryCount,
	completedSubQueryCount,
}: Props) {
	const progressPercent = subQueryCount > 0
		? Math.round((completedSubQueryCount / subQueryCount) * 100)
		: 0;

	return (
		<div className="space-y-3">
			<div>
				<div className="flex items-center justify-between text-xs text-gray-600 mb-1">
					<span>Research Progress</span>
					<span>{progressPercent}%</span>
				</div>
				<div className="w-full bg-gray-200 rounded-full h-2">
					<div
						className="bg-blue-600 h-2 rounded-full transition-all"
						style={{ width: `${progressPercent}%` }}
					/>
				</div>
			</div>

			<div className="grid grid-cols-2 md:grid-cols-4 gap-3">
				<div className="bg-blue-50 p-4 rounded-lg border border-blue-100">
					<p className="text-xs text-blue-700 font-medium uppercase tracking-wider">Sources</p>
					<p className="text-2xl font-bold text-blue-900 mt-1">{sourceCount}</p>
				</div>
				<div className="bg-green-50 p-4 rounded-lg border border-green-100">
					<p className="text-xs text-green-700 font-medium uppercase tracking-wider">Findings</p>
					<p className="text-2xl font-bold text-green-900 mt-1">{findingCount}</p>
				</div>
				<div className="bg-indigo-50 p-4 rounded-lg border border-indigo-100">
					<p className="text-xs text-indigo-700 font-medium uppercase tracking-wider">Sub-queries</p>
					<p className="text-2xl font-bold text-indigo-900 mt-1">{subQueryCount}</p>
				</div>
				<div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
					<p className="text-xs text-gray-600 font-medium uppercase tracking-wider">Status</p>
					<p className="text-lg font-bold text-gray-900 mt-1 capitalize">{status}</p>
				</div>
			</div>
		</div>
	);
}
