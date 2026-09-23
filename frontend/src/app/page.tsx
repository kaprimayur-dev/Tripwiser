export default function Home() {
  return (
    <main className="max-w-4xl mx-auto px-6 py-16">
      <header className="mb-12 text-center">
        <div className="inline-block px-3 py-1 bg-olive text-cream-100 rounded-full text-xs font-semibold uppercase tracking-wider mb-4">
          Travel Intelligence
        </div>
        <h1 className="text-5xl font-bold tracking-tight text-espresso-900 mb-4">
          TripWiser
        </h1>
        <p className="text-lg text-espresso-700 max-w-xl mx-auto">
          Find practical railway journeys across India when direct trains are unavailable.
        </p>
      </header>

      <div className="bg-white rounded-2xl p-8 border border-cream-300 shadow-sm">
        <h2 className="text-2xl font-bold text-espresso-900 mb-6">
          Find Your Journey
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div>
            <label className="block text-xs font-semibold uppercase text-espresso-700 mb-1">
              From Station
            </label>
            <input 
              type="text" 
              placeholder="e.g. Gwalior (GWL)"
              className="w-full px-4 py-3 rounded-lg border border-cream-300 bg-cream-50 text-espresso-900 focus:outline-none focus:border-terracotta"
              readOnly
            />
          </div>
          <div>
            <label className="block text-xs font-semibold uppercase text-espresso-700 mb-1">
              To Station
            </label>
            <input 
              type="text" 
              placeholder="e.g. Bhopal (BPL)"
              className="w-full px-4 py-3 rounded-lg border border-cream-300 bg-cream-50 text-espresso-900 focus:outline-none focus:border-terracotta"
              readOnly
            />
          </div>
          <div>
            <label className="block text-xs font-semibold uppercase text-espresso-700 mb-1">
              Date of Journey
            </label>
            <input 
              type="date" 
              className="w-full px-4 py-3 rounded-lg border border-cream-300 bg-cream-50 text-espresso-900 focus:outline-none focus:border-terracotta"
              readOnly
            />
          </div>
        </div>
        <button className="w-full bg-terracotta hover:bg-terracotta-hover text-white font-semibold py-4 rounded-xl transition duration-200 shadow-sm">
          Search Routes
        </button>
      </div>
    </main>
  )
}
