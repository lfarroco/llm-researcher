import { useState, useEffect, useCallback } from 'react';
import { Navigate, Route, Routes, useLocation, useNavigate, useParams } from 'react-router-dom';
import { api } from './api/client';
import type { Research } from './types';
import ResearchForm from './components/ResearchForm';
import ResearchDetail from './components/ResearchDetail';

function App() {
	const navigate = useNavigate();
	const location = useLocation();
	const [researches, setResearches] = useState<Research[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [activeTab] = useState<'research'>('research');
	const [showResearchForm, setShowResearchForm] = useState(false);

	const openResearch = (id: number) => {
		navigate(`/research/${id}`);
	};

	const loadResearches = useCallback(async (showLoading = true) => {
		try {
			if (showLoading) {
				setLoading(true);
			}
			const data = await api.listResearch(0, 100);
			setResearches(data);
			setError(null);
		} catch (err) {
			setError(err instanceof Error ? err.message : 'Failed to load researches');
		} finally {
			if (showLoading) {
				setLoading(false);
			}
		}
	}, []);

	useEffect(() => {
		loadResearches();
	}, [loadResearches]);

	useEffect(() => {
		if (location.pathname !== '/') {
			return;
		}

		// Poll list updates while on the list page only.
		const interval = setInterval(() => {
			loadResearches(false);
		}, 10000);
		return () => clearInterval(interval);
	}, [location.pathname, loadResearches]);

	const handleResearchCreated = (research: Research) => {
		setResearches([research, ...researches]);
		openResearch(research.id);
		setShowResearchForm(false);
	};

	const handleResearchDeleted = (id: number) => {
		setResearches(researches.filter(r => r.id !== id));
		navigate('/');
	};

	const ResearchTableRoute = () => (
		<div className="space-y-6">
			<div className="bg-white rounded-lg shadow p-4">
				<button
					onClick={() => setShowResearchForm((prev) => !prev)}
					className="bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 transition-colors"
				>
					{showResearchForm ? 'Close New Research' : 'New Research'}
				</button>
			</div>

			{showResearchForm && (
				<ResearchForm onResearchCreated={handleResearchCreated} />
			)}

			<div className="bg-white rounded-lg shadow overflow-hidden">
				<div className="p-4 border-b border-gray-200 flex items-center justify-between gap-4">
					<div>
						<h2 className="text-lg font-semibold text-gray-900">Research</h2>
						<p className="text-sm text-gray-600">{researches.length} items</p>
					</div>
				</div>

				{loading && researches.length === 0 ? (
					<div className="p-8 text-center text-gray-500">Loading research items...</div>
				) : researches.length === 0 ? (
					<div className="p-8 text-center text-gray-500">No research items yet.</div>
				) : (
					<div className="overflow-x-auto">
						<table className="min-w-full divide-y divide-gray-200">
							<thead className="bg-gray-50">
								<tr>
									<th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-600">Title</th>
									<th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-600">Status</th>
									<th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-600">Created</th>
									<th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-600">Updated</th>
								</tr>
							</thead>
							<tbody className="divide-y divide-gray-100 bg-white">
								{researches.map((research) => (
									<tr
										key={research.id}
										onClick={() => openResearch(research.id)}
										onKeyDown={(e) => {
											if (e.key === 'Enter' || e.key === ' ') {
												e.preventDefault();
												openResearch(research.id);
											}
										}}
										tabIndex={0}
										className="cursor-pointer hover:bg-gray-50"
									>
										<td className="px-4 py-3 text-sm text-gray-900 max-w-md">
											<button
												type="button"
												onClick={(e) => {
													e.stopPropagation();
													openResearch(research.id);
												}}
												className="text-blue-700 hover:text-blue-800 hover:underline text-left truncate w-full"
												title={research.query}
											>
												{research.query}
											</button>
										</td>
										<td className="px-4 py-3 text-sm text-gray-700 capitalize">{research.status}</td>
										<td className="px-4 py-3 text-sm text-gray-700">{new Date(research.created_at).toLocaleString()}</td>
										<td className="px-4 py-3 text-sm text-gray-700">{new Date(research.updated_at).toLocaleString()}</td>
									</tr>
								))}
							</tbody>
						</table>
					</div>
				)}
			</div>
		</div>
	);

	const ResearchDetailRoute = () => {
		const { researchId } = useParams();
		const parsedId = Number(researchId);

		if (!Number.isInteger(parsedId) || parsedId <= 0) {
			return <Navigate to="/" replace />;
		}

		const handleBack = () => {
			if (window.history.length > 1) {
				navigate(-1);
				return;
			}
			navigate('/');
		};

		return (
			<div className="space-y-4">
				<div className="bg-white rounded-lg shadow p-4">
					<button
						type="button"
						onClick={handleBack}
						className="text-blue-700 hover:text-blue-800 hover:underline"
					>
						← Back to Research
					</button>
				</div>
				<ResearchDetail
					researchId={parsedId}
					onDelete={handleResearchDeleted}
					onUpdate={loadResearches}
				/>
			</div>
		);
	};

	return (
		<div className="min-h-screen bg-gray-50">
			<header className="bg-white shadow-sm">
				<div className="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8">
					<div>
						<h1 className="text-2xl font-bold text-gray-900">🔬 LLM Researcher</h1>
						<p className="text-sm text-gray-600 mt-1">
							Autonomous AI-powered research assistant
						</p>
					</div>
				</div>
				<div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
					<nav className="flex items-end gap-1 border-b border-gray-200">
						<button
							type="button"
							className={`-mb-px px-4 py-2 text-sm font-medium border-b-2 transition-colors ${activeTab === 'research'
								? 'border-blue-600 text-blue-700'
								: 'border-transparent text-gray-500'
								}`}
						>
							Research
						</button>
					</nav>
				</div>
			</header>

			<main className="max-w-7xl mx-auto px-4 py-6 sm:px-6 lg:px-8">
				{error && (
					<div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
						{error}
					</div>
				)}

				<Routes>
					<Route path="/" element={<ResearchTableRoute />} />
					<Route path="/research/:researchId" element={<ResearchDetailRoute />} />
					<Route path="*" element={<Navigate to="/" replace />} />
				</Routes>
			</main>

			<footer className="mt-12 pb-6 text-center text-sm text-gray-500">
				<p>Built with FastAPI, LangChain, and React</p>
			</footer>
		</div>
	);
}

export default App;
