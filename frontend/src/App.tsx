import { useState, useEffect } from 'react';
import { api } from './api/client';
import type { Research } from './types';
import ResearchForm from './components/ResearchForm';
import ResearchList from './components/ResearchList';
import ResearchDetail from './components/ResearchDetail';

function App() {
	const [researches, setResearches] = useState<Research[]>([]);
	const [selectedResearch, setSelectedResearch] = useState<number | null>(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	const loadResearches = async () => {
		try {
			setLoading(true);
			const data = await api.listResearch();
			setResearches(data);
			setError(null);
		} catch (err) {
			setError(err instanceof Error ? err.message : 'Failed to load researches');
		} finally {
			setLoading(false);
		}
	};

	useEffect(() => {
		loadResearches();
		// Poll for updates every 10 seconds
		const interval = setInterval(loadResearches, 10000);
		return () => clearInterval(interval);
	}, []);

	const handleResearchCreated = (research: Research) => {
		setResearches([research, ...researches]);
		setSelectedResearch(research.id);
	};

	const handleResearchDeleted = (id: number) => {
		setResearches(researches.filter(r => r.id !== id));
		if (selectedResearch === id) {
			setSelectedResearch(null);
		}
	};

	return (
		<div className="min-h-screen bg-gray-50">
			<header className="bg-white shadow-sm">
				<div className="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8">
					<h1 className="text-2xl font-bold text-gray-900">🔬 LLM Researcher</h1>
					<p className="text-sm text-gray-600 mt-1">
						Autonomous AI-powered research assistant
					</p>
				</div>
			</header>

			<main className="max-w-7xl mx-auto px-4 py-6 sm:px-6 lg:px-8">
				{error && (
					<div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
						{error}
					</div>
				)}

				<div className="mb-6">
					<ResearchForm onResearchCreated={handleResearchCreated} />
				</div>

				<div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
					<div className="lg:col-span-1">
						<ResearchList
							researches={researches}
							selectedId={selectedResearch}
							onSelect={setSelectedResearch}
							loading={loading}
						/>
					</div>

					<div className="lg:col-span-2">
						{selectedResearch ? (
							<ResearchDetail
								researchId={selectedResearch}
								onDelete={handleResearchDeleted}
								onUpdate={loadResearches}
							/>
						) : (
							<div className="bg-white rounded-lg shadow p-12 text-center text-gray-500">
								<p className="text-lg">Select a research query to view details</p>
								<p className="text-sm mt-2">or create a new one above</p>
							</div>
						)}
					</div>
				</div>
			</main>

			<footer className="mt-12 pb-6 text-center text-sm text-gray-500">
				<p>Built with FastAPI, LangChain, and React</p>
			</footer>
		</div>
	);
}

export default App;
