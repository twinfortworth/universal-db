import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Search, Rss, Globe, Calendar, ExternalLink, Loader2 } from 'lucide-react'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface RSSItem {
  uuid: string
  created_at: string
  data: {
    title: string
    description?: string
    link: string
    published?: string
    content?: string
    author?: string
    tags?: string[]
  }
}

interface SearchResult {
  uuid: string
  title: string
  description?: string
  link: string
  score: number
  published?: string
}

function App() {
  const [feedUrl, setFeedUrl] = useState('')
  const [tenantId, setTenantId] = useState('default')
  const [searchQuery, setSearchQuery] = useState('')
  const [records, setRecords] = useState<RSSItem[]>([])
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const [searching, setSearching] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)
  const [activeTab, setActiveTab] = useState<'ingest' | 'browse' | 'search'>('ingest')

  const showMessage = (type: 'success' | 'error', text: string) => {
    setMessage({ type, text })
    setTimeout(() => setMessage(null), 5000)
  }

  const handleIngestRSS = async () => {
    if (!feedUrl.trim()) {
      showMessage('error', 'Please enter a valid RSS feed URL')
      return
    }

    setLoading(true)
    try {
      const response = await fetch(`${API_URL}/ingest/rss`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          feed_url: feedUrl,
          tenant_id: tenantId
        })
      })

      const result = await response.json()
      
      if (response.ok) {
        showMessage('success', `Successfully ingested ${result.processed_items} items from ${result.feed_title}`)
        setFeedUrl('')
        if (activeTab === 'browse') {
          loadRecords()
        }
      } else {
        showMessage('error', result.detail || 'Failed to ingest RSS feed')
      }
    } catch (error) {
      showMessage('error', 'Failed to connect to the server. Make sure the backend is running.')
    } finally {
      setLoading(false)
    }
  }

  const loadRecords = async () => {
    try {
      const response = await fetch(`${API_URL}/records?tenant_id=${tenantId}&limit=20`)
      const result = await response.json()
      
      if (response.ok) {
        setRecords(result.records)
      } else {
        showMessage('error', 'Failed to load records')
      }
    } catch (error) {
      showMessage('error', 'Failed to connect to the server')
    }
  }

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      showMessage('error', 'Please enter a search query')
      return
    }

    setSearching(true)
    try {
      const response = await fetch(`${API_URL}/search`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: searchQuery,
          tenant_id: tenantId,
          limit: 10
        })
      })

      const result = await response.json()
      
      if (response.ok) {
        setSearchResults(result.results)
        if (result.results.length === 0) {
          showMessage('error', 'No results found for your search query')
        }
      } else {
        showMessage('error', result.detail || 'Search failed')
      }
    } catch (error) {
      showMessage('error', 'Failed to connect to the server')
    } finally {
      setSearching(false)
    }
  }

  useEffect(() => {
    if (activeTab === 'browse') {
      loadRecords()
    }
  }, [activeTab, tenantId])

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'Unknown date'
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto px-4 py-8 max-w-6xl">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2 flex items-center gap-3">
            <Rss className="text-orange-500" />
            Universal Database - RSS Ingestion
          </h1>
          <p className="text-gray-600">
            Ingest RSS feeds, store them in a universal format, and search through articles using semantic search.
          </p>
        </div>

        {/* Message Alert */}
        {message && (
          <Alert className={`mb-6 ${message.type === 'error' ? 'border-red-200 bg-red-50' : 'border-green-200 bg-green-50'}`}>
            <AlertDescription className={message.type === 'error' ? 'text-red-800' : 'text-green-800'}>
              {message.text}
            </AlertDescription>
          </Alert>
        )}

        {/* Navigation Tabs */}
        <div className="flex gap-2 mb-6">
          <Button
            variant={activeTab === 'ingest' ? 'default' : 'outline'}
            onClick={() => setActiveTab('ingest')}
            className="flex items-center gap-2"
          >
            <Rss size={16} />
            Ingest RSS
          </Button>
          <Button
            variant={activeTab === 'browse' ? 'default' : 'outline'}
            onClick={() => setActiveTab('browse')}
            className="flex items-center gap-2"
          >
            <Globe size={16} />
            Browse Articles
          </Button>
          <Button
            variant={activeTab === 'search' ? 'default' : 'outline'}
            onClick={() => setActiveTab('search')}
            className="flex items-center gap-2"
          >
            <Search size={16} />
            Search
          </Button>
        </div>

        {/* Tenant ID Input */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-lg">Configuration</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-4">
              <label className="text-sm font-medium text-gray-700">Tenant ID:</label>
              <Input
                value={tenantId}
                onChange={(e) => setTenantId(e.target.value)}
                placeholder="default"
                className="w-48"
              />
            </div>
          </CardContent>
        </Card>

        {/* RSS Ingestion Tab */}
        {activeTab === 'ingest' && (
          <Card>
            <CardHeader>
              <CardTitle>Ingest RSS Feed</CardTitle>
              <CardDescription>
                Enter an RSS feed URL to parse and store all articles in the universal database format.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-sm font-medium text-gray-700 mb-2 block">RSS Feed URL</label>
                <Input
                  value={feedUrl}
                  onChange={(e) => setFeedUrl(e.target.value)}
                  placeholder="https://feeds.bbci.co.uk/news/rss.xml"
                  className="w-full"
                />
              </div>
              <Button 
                onClick={handleIngestRSS} 
                disabled={loading}
                className="w-full"
              >
                {loading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Ingesting RSS Feed...
                  </>
                ) : (
                  <>
                    <Rss className="mr-2 h-4 w-4" />
                    Ingest RSS Feed
                  </>
                )}
              </Button>
              
              <div className="mt-6 p-4 bg-blue-50 rounded-lg">
                <h4 className="font-medium text-blue-900 mb-2">Try these sample RSS feeds:</h4>
                <div className="space-y-1 text-sm">
                  <button 
                    onClick={() => setFeedUrl('https://feeds.bbci.co.uk/news/rss.xml')}
                    className="block text-blue-600 hover:text-blue-800 underline"
                  >
                    BBC News
                  </button>
                  <button 
                    onClick={() => setFeedUrl('https://techcrunch.com/feed/')}
                    className="block text-blue-600 hover:text-blue-800 underline"
                  >
                    TechCrunch
                  </button>
                  <button 
                    onClick={() => setFeedUrl('https://rss.cnn.com/rss/edition.rss')}
                    className="block text-blue-600 hover:text-blue-800 underline"
                  >
                    CNN
                  </button>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Browse Articles Tab */}
        {activeTab === 'browse' && (
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <h2 className="text-2xl font-bold">Stored Articles</h2>
              <Button onClick={loadRecords} variant="outline">
                Refresh
              </Button>
            </div>
            
            {records.length === 0 ? (
              <Card>
                <CardContent className="py-8 text-center">
                  <p className="text-gray-500">No articles found. Try ingesting an RSS feed first.</p>
                </CardContent>
              </Card>
            ) : (
              <div className="grid gap-4">
                {records.map((record) => (
                  <Card key={record.uuid} className="hover:shadow-md transition-shadow">
                    <CardContent className="pt-6">
                      <div className="flex justify-between items-start mb-3">
                        <h3 className="text-lg font-semibold text-gray-900 leading-tight">
                          {record.data.title}
                        </h3>
                        <a
                          href={record.data.link}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:text-blue-800 ml-4"
                        >
                          <ExternalLink size={16} />
                        </a>
                      </div>
                      
                      {record.data.description && (
                        <p className="text-gray-600 mb-3 line-clamp-2">
                          {record.data.description}
                        </p>
                      )}
                      
                      <div className="flex items-center gap-4 text-sm text-gray-500">
                        <div className="flex items-center gap-1">
                          <Calendar size={14} />
                          {formatDate(record.data.published)}
                        </div>
                        {record.data.author && (
                          <span>by {record.data.author}</span>
                        )}
                      </div>
                      
                      {record.data.tags && record.data.tags.length > 0 && (
                        <div className="flex gap-2 mt-3">
                          {record.data.tags.slice(0, 3).map((tag, index) => (
                            <Badge key={index} variant="secondary" className="text-xs">
                              {tag}
                            </Badge>
                          ))}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Search Tab */}
        {activeTab === 'search' && (
          <div className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Semantic Search</CardTitle>
                <CardDescription>
                  Search through ingested articles using natural language queries.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <label className="text-sm font-medium text-gray-700 mb-2 block">Search Query</label>
                  <Textarea
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Enter your search query (e.g., 'technology news', 'climate change', 'artificial intelligence')"
                    className="w-full"
                    rows={3}
                  />
                </div>
                <Button 
                  onClick={handleSearch} 
                  disabled={searching}
                  className="w-full"
                >
                  {searching ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Searching...
                    </>
                  ) : (
                    <>
                      <Search className="mr-2 h-4 w-4" />
                      Search Articles
                    </>
                  )}
                </Button>
              </CardContent>
            </Card>

            {/* Search Results */}
            {searchResults.length > 0 && (
              <div className="space-y-4">
                <h3 className="text-xl font-semibold">Search Results</h3>
                <div className="grid gap-4">
                  {searchResults.map((result) => (
                    <Card key={result.uuid} className="hover:shadow-md transition-shadow">
                      <CardContent className="pt-6">
                        <div className="flex justify-between items-start mb-3">
                          <h4 className="text-lg font-semibold text-gray-900 leading-tight">
                            {result.title}
                          </h4>
                          <div className="flex items-center gap-2 ml-4">
                            <Badge variant="outline" className="text-xs">
                              {Math.round(result.score * 100)}% match
                            </Badge>
                            <a
                              href={result.link}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-blue-600 hover:text-blue-800"
                            >
                              <ExternalLink size={16} />
                            </a>
                          </div>
                        </div>
                        
                        {result.description && (
                          <p className="text-gray-600 mb-3">
                            {result.description}
                          </p>
                        )}
                        
                        <div className="flex items-center gap-4 text-sm text-gray-500">
                          <div className="flex items-center gap-1">
                            <Calendar size={14} />
                            {formatDate(result.published)}
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default App
