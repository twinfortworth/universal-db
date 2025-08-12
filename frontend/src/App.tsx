import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Search, Rss, Globe, Calendar, ExternalLink, Loader2, Plus, Settings, CheckCircle, XCircle, Clock, Edit, Trash2, Database } from 'lucide-react'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Switch } from '@/components/ui/switch'
import { Pagination, PaginationContent, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious } from '@/components/ui/pagination'
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
    relevance_score?: number
    entities?: Array<{
      name: string
      type: string
      confidence: number
    }>
    domain_tags?: string[]
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

interface Domain {
  domain_id: string
  name: string
  description: string
  keywords: string[]
  entities: string[]
  locations: string[]
  exclude_keywords: string[]
  min_relevance_score: number
}

interface UpdateSchedule {
  frequency: 'hourly' | 'daily' | 'weekly' | 'monthly'
  time_of_day?: string
  day_of_week?: number
  day_of_month?: number
  next_update?: string
}

interface RSSFeed {
  feed_id: string
  name: string
  url: string
  domain_id?: string
  tenant_id: string
  is_active: boolean
  status: 'active' | 'inactive' | 'error' | 'pending'
  schedule: UpdateSchedule
  last_update?: string
  last_error?: string
  total_articles: number
  successful_updates: number
  failed_updates: number
  created_at: string
  updated_at: string
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
  const [activeTab, setActiveTab] = useState<'ingest' | 'domain' | 'browse' | 'search' | 'manage'>('ingest')
  const [domains, setDomains] = useState<Domain[]>([])
  const [selectedDomain, setSelectedDomain] = useState('fort_worth_political')
  const [showCreateDomain, setShowCreateDomain] = useState(false)
  const [newDomain, setNewDomain] = useState({
    name: '',
    description: '',
    keywords: '',
    entities: '',
    locations: '',
    exclude_keywords: '',
    min_relevance_score: 0.3
  })
  const [rssFeeds, setRssFeeds] = useState<RSSFeed[]>([])
  const [showCreateFeed, setShowCreateFeed] = useState(false)
  const [showEditFeed, setShowEditFeed] = useState(false)
  const [editingFeed, setEditingFeed] = useState<RSSFeed | null>(null)
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [updatingFeeds, setUpdatingFeeds] = useState<Set<string>>(new Set())
  const [newFeed, setNewFeed] = useState({
    name: '',
    url: '',
    domain_id: 'none',
    schedule: {
      frequency: 'daily' as const,
      time_of_day: '09:00'
    }
  })

  const showMessage = (type: 'success' | 'error', text: string) => {
    setMessage({ type, text })
    setTimeout(() => setMessage(null), 5000)
  }

  const loadDomains = async () => {
    try {
      const response = await fetch(`${API_URL}/domains`)
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      const data = await response.json()
      setDomains(data.domains || [])
    } catch (error) {
      console.error('Failed to load domains:', error)
      setDomains([])
      showMessage('error', 'Failed to load domains')
    }
  }

  const handleCreateDomain = async () => {
    try {
      const domainData = {
        name: newDomain.name,
        description: newDomain.description,
        keywords: newDomain.keywords.split(',').map(k => k.trim()).filter(k => k),
        entities: newDomain.entities.split(',').map(e => e.trim()).filter(e => e),
        locations: newDomain.locations.split(',').map(l => l.trim()).filter(l => l),
        exclude_keywords: newDomain.exclude_keywords.split(',').map(e => e.trim()).filter(e => e),
        min_relevance_score: newDomain.min_relevance_score,
        entity_patterns: {
          person: ["\\b[A-Z][a-z]+ [A-Z][a-z]+\\b"],
          organization: ["\\b[A-Z][a-zA-Z ]+(?:Inc|Corp|LLC|Ltd)\\b"],
          location: ["\\b[A-Z][a-zA-Z ]+(?:City|County|State)\\b"]
        }
      }
      
      const response = await fetch(`${API_URL}/domains`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(domainData)
      })
      
      if (response.ok) {
        showMessage('success', 'Domain created successfully!')
        setShowCreateDomain(false)
        setNewDomain({
          name: '',
          description: '',
          keywords: '',
          entities: '',
          locations: '',
          exclude_keywords: '',
          min_relevance_score: 0.3
        })
        loadDomains()
      } else {
        showMessage('error', 'Failed to create domain')
      }
    } catch (error) {
      showMessage('error', 'Failed to create domain')
    }
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

  const handleDomainIngest = async () => {
    if (!feedUrl.trim()) {
      showMessage('error', 'Please enter a valid RSS feed URL')
      return
    }

    setLoading(true)
    try {
      const response = await fetch(`${API_URL}/ingest/rss/domain`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          feed_url: feedUrl,
          tenant_id: tenantId,
          domain_id: selectedDomain,
          extract_entities: true
        })
      })

      const result = await response.json()
      if (response.ok) {
        if (result.processed_items === 0 && result.filtered_out > 0) {
          showMessage('error', `No articles matched the ${result.domain_name} domain criteria. ${result.filtered_out} articles were filtered out. Try adjusting the domain keywords or using a different RSS feed.`)
        } else if (result.processed_items === 0) {
          showMessage('error', `No articles were processed from ${result.domain_name} domain. The RSS feed may be empty or incompatible.`)
        } else {
          showMessage('success', `Successfully ingested ${result.processed_items} articles from ${result.domain_name} domain! (${result.filtered_out} filtered out)`)
        }
        setFeedUrl('')
        if (activeTab === 'browse') {
          loadRecords()
        }
      } else {
        showMessage('error', result.detail || 'Failed to ingest RSS feed')
      }
    } catch (error) {
      showMessage('error', 'Failed to connect to the server')
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
    loadDomains()
    if (activeTab === 'manage') {
      loadRssFeeds()
    }
  }, [activeTab])

  useEffect(() => {
    if (activeTab === 'manage') {
      loadRssFeeds()
    }
  }, [currentPage])

  useEffect(() => {
    if (activeTab === 'browse') {
      loadRecords()
    } else if (activeTab === 'manage') {
      loadRssFeeds()
    }
  }, [activeTab, tenantId])

  useEffect(() => {
    if (activeTab === 'manage') {
      loadRssFeeds()
    }
  }, [currentPage])

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'Never'
    try {
      return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      })
    } catch {
      return 'Invalid date'
    }
  }

  const loadRssFeeds = async () => {
    try {
      const response = await fetch(`${API_URL}/feeds?tenant_id=${tenantId}&page=${currentPage}&page_size=10`)
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      const data = await response.json()
      setRssFeeds(data.feeds || [])
      setTotalPages(Math.ceil(data.total / 10))
    } catch (error) {
      console.error('Failed to load RSS feeds:', error)
      setRssFeeds([])
      showMessage('error', 'Failed to load RSS feeds')
    }
  }

  const handleCreateFeed = async () => {
    if (!newFeed.name || !newFeed.url) {
      showMessage('error', 'Please fill in all required fields')
      return
    }

    setLoading(true)
    try {
      const response = await fetch(`${API_URL}/feeds`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...newFeed,
          tenant_id: tenantId,
          is_active: true,
          domain_id: newFeed.domain_id === 'none' ? null : newFeed.domain_id
        })
      })

      if (response.ok) {
        showMessage('success', 'RSS feed created successfully')
        setShowCreateFeed(false)
        setNewFeed({
          name: '',
          url: '',
          domain_id: 'none',
          schedule: {
            frequency: 'daily' as const,
            time_of_day: '09:00'
          }
        })
        loadRssFeeds()
      } else {
        const error = await response.json()
        showMessage('error', error.detail || 'Failed to create RSS feed')
      }
    } catch (error) {
      console.error('Failed to create RSS feed:', error)
      showMessage('error', 'Failed to connect to the server')
    } finally {
      setLoading(false)
    }
  }

  const toggleFeedStatus = async (feedId: string) => {
    try {
      const response = await fetch(`${API_URL}/feeds/${feedId}/toggle`, {
        method: 'POST'
      })
      if (response.ok) {
        loadRssFeeds()
      } else {
        showMessage('error', 'Failed to toggle feed status')
      }
    } catch (error) {
      console.error('Failed to toggle feed status:', error)
      showMessage('error', 'Failed to connect to the server')
    }
  }

  const updateFeedManually = async (feedId: string) => {
    setUpdatingFeeds(prev => new Set(prev).add(feedId))
    try {
      const response = await fetch(`${API_URL}/feeds/${feedId}/update`, {
        method: 'POST'
      })
      const result = await response.json()
      if (result.success) {
        showMessage('success', `Updated successfully: ${result.articles_processed} articles processed`)
      } else {
        showMessage('error', result.error_message || 'Update failed')
      }
      loadRssFeeds()
    } catch (error) {
      console.error('Failed to update feed:', error)
      showMessage('error', 'Failed to connect to the server')
    } finally {
      setUpdatingFeeds(prev => {
        const newSet = new Set(prev)
        newSet.delete(feedId)
        return newSet
      })
    }
  }

  const deleteFeed = async (feedId: string) => {
    if (!confirm('Are you sure you want to delete this RSS feed?')) {
      return
    }

    try {
      const response = await fetch(`${API_URL}/feeds/${feedId}`, {
        method: 'DELETE'
      })
      if (response.ok) {
        showMessage('success', 'RSS feed deleted successfully')
        loadRssFeeds()
      } else {
        showMessage('error', 'Failed to delete RSS feed')
      }
    } catch (error) {
      console.error('Failed to delete feed:', error)
      showMessage('error', 'Failed to connect to the server')
    }
  }

  const editFeed = (feed: RSSFeed) => {
    setEditingFeed(feed)
    setShowEditFeed(true)
  }

  const handleEditFeed = async () => {
    if (!editingFeed) return

    setLoading(true)
    try {
      const response = await fetch(`${API_URL}/feeds/${editingFeed.feed_id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: editingFeed.name,
          url: editingFeed.url,
          domain_id: editingFeed.domain_id,
          schedule: editingFeed.schedule
        })
      })

      if (response.ok) {
        showMessage('success', 'RSS feed updated successfully')
        setShowEditFeed(false)
        setEditingFeed(null)
        loadRssFeeds()
      } else {
        const error = await response.json()
        showMessage('error', error.detail || 'Failed to update RSS feed')
      }
    } catch (error) {
      console.error('Failed to update RSS feed:', error)
      showMessage('error', 'Failed to connect to the server')
    } finally {
      setLoading(false)
    }
  }

  const getDomainName = (domainId?: string) => {
    if (!domainId) return 'None'
    const domain = domains.find(d => d.domain_id === domainId)
    return domain ? domain.name : 'Unknown'
  }

  const getStatusVariant = (status: string) => {
    switch (status) {
      case 'active': return 'default'
      case 'error': return 'destructive'
      case 'pending': return 'secondary'
      default: return 'outline'
    }
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
            Basic RSS
          </Button>
          <Button
            variant={activeTab === 'domain' ? 'default' : 'outline'}
            onClick={() => setActiveTab('domain')}
            className="flex items-center gap-2"
          >
            <Settings size={16} />
            Domain RSS
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
          <Button
            variant={activeTab === 'manage' ? 'default' : 'outline'}
            onClick={() => setActiveTab('manage')}
            className="flex items-center gap-2"
          >
            <Database size={16} />
            RSS Management
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

        {/* Basic RSS Ingestion Tab */}
        {activeTab === 'ingest' && (
          <Card>
            <CardHeader>
              <CardTitle>Basic RSS Feed Ingestion</CardTitle>
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

        {/* Domain-Specific RSS Ingestion Tab */}
        {activeTab === 'domain' && (
          <Card>
            <CardHeader>
              <CardTitle>Domain-Specific RSS Ingestion</CardTitle>
              <CardDescription>
                Ingest RSS feeds with domain-specific filtering, entity recognition, and relevance scoring.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-sm font-medium text-gray-700 mb-2 block">Select Domain</label>
                <Select value={selectedDomain} onValueChange={setSelectedDomain}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select a domain" />
                  </SelectTrigger>
                  <SelectContent>
                    {domains.filter(domain => domain.domain_id && domain.domain_id.trim() !== '').map(domain => (
                      <SelectItem key={domain.domain_id} value={domain.domain_id}>
                        {domain.name} - {domain.description}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              
              <div className="flex gap-2">
                <Dialog open={showCreateDomain} onOpenChange={setShowCreateDomain}>
                  <DialogTrigger asChild>
                    <Button variant="outline">
                      <Plus className="w-4 h-4 mr-2" />
                      Create New Domain
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="max-w-2xl">
                    <DialogHeader>
                      <DialogTitle>Create New Domain</DialogTitle>
                      <DialogDescription>
                        Define a new domain template for content filtering and entity recognition.
                      </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4">
                      <div>
                        <Label htmlFor="domain-name">Domain Name</Label>
                        <Input
                          id="domain-name"
                          placeholder="e.g., Tech Startup News"
                          value={newDomain.name}
                          onChange={(e) => setNewDomain({...newDomain, name: e.target.value})}
                        />
                      </div>
                      <div>
                        <Label htmlFor="domain-description">Description</Label>
                        <Input
                          id="domain-description"
                          placeholder="e.g., Technology startup and venture capital news"
                          value={newDomain.description}
                          onChange={(e) => setNewDomain({...newDomain, description: e.target.value})}
                        />
                      </div>
                      <div>
                        <Label htmlFor="domain-keywords">Keywords (comma-separated)</Label>
                        <Textarea
                          id="domain-keywords"
                          placeholder="e.g., startup, venture capital, tech, funding, IPO"
                          value={newDomain.keywords}
                          onChange={(e) => setNewDomain({...newDomain, keywords: e.target.value})}
                        />
                      </div>
                      <div>
                        <Label htmlFor="domain-entities">Known Entities (comma-separated)</Label>
                        <Textarea
                          id="domain-entities"
                          placeholder="e.g., Y Combinator, Andreessen Horowitz, Sequoia Capital"
                          value={newDomain.entities}
                          onChange={(e) => setNewDomain({...newDomain, entities: e.target.value})}
                        />
                      </div>
                      <div>
                        <Label htmlFor="domain-locations">Locations (comma-separated)</Label>
                        <Textarea
                          id="domain-locations"
                          placeholder="e.g., Silicon Valley, San Francisco, Palo Alto"
                          value={newDomain.locations}
                          onChange={(e) => setNewDomain({...newDomain, locations: e.target.value})}
                        />
                      </div>
                      <div>
                        <Label htmlFor="domain-exclude">Exclude Keywords (comma-separated)</Label>
                        <Textarea
                          id="domain-exclude"
                          placeholder="e.g., sports, entertainment, celebrity"
                          value={newDomain.exclude_keywords}
                          onChange={(e) => setNewDomain({...newDomain, exclude_keywords: e.target.value})}
                        />
                      </div>
                      <div>
                        <Label htmlFor="min-relevance">Minimum Relevance Score (0.0 - 1.0)</Label>
                        <Input
                          id="min-relevance"
                          type="number"
                          min="0"
                          max="1"
                          step="0.1"
                          value={newDomain.min_relevance_score}
                          onChange={(e) => setNewDomain({...newDomain, min_relevance_score: parseFloat(e.target.value)})}
                        />
                      </div>
                      <Button onClick={handleCreateDomain} className="w-full">
                        Create Domain
                      </Button>
                    </div>
                  </DialogContent>
                </Dialog>
              </div>
              
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
                onClick={handleDomainIngest} 
                disabled={loading}
                className="w-full"
              >
                {loading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Ingesting with Domain Filter...
                  </>
                ) : (
                  <>
                    <Settings className="mr-2 h-4 w-4" />
                    Ingest with Domain Filter
                  </>
                )}
              </Button>
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
                        {record.data.relevance_score && (
                          <Badge variant="outline" className="text-xs">
                            Relevance: {(record.data.relevance_score * 100).toFixed(0)}%
                          </Badge>
                        )}
                      </div>
                      
                      {record.data.entities && record.data.entities.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-3">
                          <span className="text-xs text-gray-500">Entities:</span>
                          {record.data.entities.slice(0, 3).map((entity, entityIndex) => (
                            <Badge key={entityIndex} variant="secondary" className="text-xs">
                              {entity.name} ({entity.type})
                            </Badge>
                          ))}
                        </div>
                      )}
                      
                      {record.data.domain_tags && record.data.domain_tags.length > 0 && (
                        <div className="flex gap-2 mt-3">
                          {record.data.domain_tags.map((tag, tagIndex) => (
                            <Badge key={tagIndex} variant="default" className="text-xs">
                              {tag}
                            </Badge>
                          ))}
                        </div>
                      )}
                      
                      {record.data.tags && record.data.tags.length > 0 && (
                        <div className="flex gap-2 mt-3">
                          {record.data.tags.slice(0, 3).map((tag, index) => (
                            <Badge key={index} variant="outline" className="text-xs">
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

        {/* RSS Management Tab */}
        {activeTab === 'manage' && (
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <h2 className="text-2xl font-bold">RSS Feed Management</h2>
              <Button onClick={() => setShowCreateFeed(true)}>
                <Plus className="w-4 h-4 mr-2" />
                Add RSS Feed
              </Button>
            </div>
            
            {rssFeeds.length === 0 ? (
              <Card>
                <CardContent className="py-8 text-center">
                  <p className="text-gray-500">No RSS feeds found. Create your first RSS feed to get started.</p>
                </CardContent>
              </Card>
            ) : (
              <Card>
                <CardContent className="p-0">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Name</TableHead>
                        <TableHead>URL</TableHead>
                        <TableHead>Domain</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>On/Off</TableHead>
                        <TableHead>Last Update</TableHead>
                        <TableHead>Success/Failure</TableHead>
                        <TableHead>Schedule</TableHead>
                        <TableHead>Next Update</TableHead>
                        <TableHead>Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {rssFeeds.map((feed) => (
                        <TableRow key={feed.feed_id}>
                          <TableCell className="font-medium">{feed.name}</TableCell>
                          <TableCell className="max-w-xs truncate" title={feed.url}>{feed.url}</TableCell>
                          <TableCell>{getDomainName(feed.domain_id)}</TableCell>
                          <TableCell>
                            <Badge variant={getStatusVariant(feed.status)}>
                              {feed.status}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            <Switch
                              checked={feed.is_active}
                              onCheckedChange={() => toggleFeedStatus(feed.feed_id)}
                            />
                          </TableCell>
                          <TableCell>{formatDate(feed.last_update)}</TableCell>
                          <TableCell>
                            {feed.status === 'active' ? (
                              <CheckCircle className="w-4 h-4 text-green-500" />
                            ) : feed.status === 'error' ? (
                              <XCircle className="w-4 h-4 text-red-500" />
                            ) : (
                              <Clock className="w-4 h-4 text-gray-400" />
                            )}
                          </TableCell>
                          <TableCell>{feed.schedule.frequency}</TableCell>
                          <TableCell>{formatDate(feed.schedule.next_update)}</TableCell>
                          <TableCell>
                            <div className="flex gap-2">
                              <Button size="sm" onClick={() => updateFeedManually(feed.feed_id)} disabled={updatingFeeds.has(feed.feed_id)}>
                                {updatingFeeds.has(feed.feed_id) ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Update Now'}
                              </Button>
                              <Button size="sm" variant="outline" onClick={() => editFeed(feed)}>
                                <Edit className="w-3 h-3" />
                              </Button>
                              <Button size="sm" variant="destructive" onClick={() => deleteFeed(feed.feed_id)}>
                                <Trash2 className="w-3 h-3" />
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            )}

            {totalPages > 1 && (
              <Pagination>
                <PaginationContent>
                  <PaginationItem>
                    <PaginationPrevious 
                      onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                      className={currentPage === 1 ? 'pointer-events-none opacity-50' : 'cursor-pointer'}
                    />
                  </PaginationItem>
                  {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
                    <PaginationItem key={page}>
                      <PaginationLink
                        onClick={() => setCurrentPage(page)}
                        isActive={currentPage === page}
                        className="cursor-pointer"
                      >
                        {page}
                      </PaginationLink>
                    </PaginationItem>
                  ))}
                  <PaginationItem>
                    <PaginationNext 
                      onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
                      className={currentPage === totalPages ? 'pointer-events-none opacity-50' : 'cursor-pointer'}
                    />
                  </PaginationItem>
                </PaginationContent>
              </Pagination>
            )}

            {/* Create RSS Feed Dialog */}
            <Dialog open={showCreateFeed} onOpenChange={setShowCreateFeed}>
              <DialogContent className="max-w-2xl">
                <DialogHeader>
                  <DialogTitle>Create RSS Feed</DialogTitle>
                  <DialogDescription>
                    Add a new RSS feed with scheduling and domain filtering options.
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4">
                  <div>
                    <Label htmlFor="feed-name">Feed Name *</Label>
                    <Input
                      id="feed-name"
                      placeholder="e.g., Tech News Daily"
                      value={newFeed.name}
                      onChange={(e) => setNewFeed({...newFeed, name: e.target.value})}
                    />
                  </div>
                  <div>
                    <Label htmlFor="feed-url">RSS Feed URL *</Label>
                    <Input
                      id="feed-url"
                      placeholder="https://example.com/rss.xml"
                      value={newFeed.url}
                      onChange={(e) => setNewFeed({...newFeed, url: e.target.value})}
                    />
                  </div>
                  <div>
                    <Label htmlFor="feed-domain">Domain (Optional)</Label>
                    <Select value={newFeed.domain_id} onValueChange={(value) => setNewFeed({...newFeed, domain_id: value})}>
                      <SelectTrigger>
                        <SelectValue placeholder="Select a domain" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">No domain filter</SelectItem>
                        {domains.filter(domain => domain.domain_id && domain.domain_id.trim() !== '').map(domain => (
                          <SelectItem key={domain.domain_id} value={domain.domain_id}>
                            {domain.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label htmlFor="update-frequency">Update Frequency</Label>
                    <Select value={newFeed.schedule.frequency} onValueChange={(value) => setNewFeed({...newFeed, schedule: {...newFeed.schedule, frequency: value as any}})}>
                      <SelectTrigger>
                        <SelectValue placeholder="Select frequency" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="hourly">Hourly</SelectItem>
                        <SelectItem value="daily">Daily</SelectItem>
                        <SelectItem value="weekly">Weekly</SelectItem>
                        <SelectItem value="monthly">Monthly</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label htmlFor="time-of-day">Time of Day (HH:MM)</Label>
                    <Input
                      id="time-of-day"
                      placeholder="14:30"
                      value={newFeed.schedule.time_of_day}
                      onChange={(e) => setNewFeed({...newFeed, schedule: {...newFeed.schedule, time_of_day: e.target.value}})}
                    />
                  </div>
                  <Button onClick={handleCreateFeed} className="w-full" disabled={loading}>
                    {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                    Create RSS Feed
                  </Button>
                </div>
              </DialogContent>
            </Dialog>

            {/* Edit RSS Feed Dialog */}
            <Dialog open={showEditFeed} onOpenChange={setShowEditFeed}>
              <DialogContent className="max-w-2xl">
                <DialogHeader>
                  <DialogTitle>Edit RSS Feed</DialogTitle>
                  <DialogDescription>
                    Update RSS feed configuration and scheduling options.
                  </DialogDescription>
                </DialogHeader>
                {editingFeed && (
                  <div className="space-y-4">
                    <div>
                      <Label htmlFor="edit-feed-name">Feed Name *</Label>
                      <Input
                        id="edit-feed-name"
                        placeholder="e.g., Tech News Daily"
                        value={editingFeed.name}
                        onChange={(e) => setEditingFeed({...editingFeed, name: e.target.value})}
                      />
                    </div>
                    <div>
                      <Label htmlFor="edit-feed-url">RSS Feed URL *</Label>
                      <Input
                        id="edit-feed-url"
                        placeholder="https://example.com/rss.xml"
                        value={editingFeed.url}
                        onChange={(e) => setEditingFeed({...editingFeed, url: e.target.value})}
                      />
                    </div>
                    <div>
                      <Label htmlFor="edit-feed-domain">Domain (Optional)</Label>
                      <Select value={editingFeed.domain_id || 'none'} onValueChange={(value) => setEditingFeed({...editingFeed, domain_id: value === 'none' ? undefined : value})}>
                        <SelectTrigger>
                          <SelectValue placeholder="Select a domain" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="none">No domain filter</SelectItem>
                          {domains.filter(domain => domain.domain_id && domain.domain_id.trim() !== '').map(domain => (
                            <SelectItem key={domain.domain_id} value={domain.domain_id}>
                              {domain.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label htmlFor="edit-update-frequency">Update Frequency</Label>
                      <Select value={editingFeed.schedule.frequency} onValueChange={(value) => setEditingFeed({...editingFeed, schedule: {...editingFeed.schedule, frequency: value as any}})}>
                        <SelectTrigger>
                          <SelectValue placeholder="Select frequency" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="hourly">Hourly</SelectItem>
                          <SelectItem value="daily">Daily</SelectItem>
                          <SelectItem value="weekly">Weekly</SelectItem>
                          <SelectItem value="monthly">Monthly</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label htmlFor="edit-time-of-day">Time of Day (HH:MM)</Label>
                      <Input
                        id="edit-time-of-day"
                        placeholder="14:30"
                        value={editingFeed.schedule.time_of_day || ''}
                        onChange={(e) => setEditingFeed({...editingFeed, schedule: {...editingFeed.schedule, time_of_day: e.target.value}})}
                      />
                    </div>
                    <Button onClick={handleEditFeed} className="w-full" disabled={loading}>
                      {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                      Update RSS Feed
                    </Button>
                  </div>
                )}
              </DialogContent>
            </Dialog>
          </div>
        )}
      </div>
    </div>
  )
}

export default App
