import { useState, useEffect, useRef } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { LogOut, Send, Loader2, Calendar } from "lucide-react"
import Markdown from "react-markdown"

const CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string
const API_KEY = import.meta.env.VITE_GOOGLE_API_KEY as string
const SCOPES = import.meta.env.VITE_GOOGLE_SCOPES as string

declare global {
  interface Window {
    gapi: any
    google: any
  }
}

interface ChatMessage {
  role: string
  text: string
}

function App() {
  const modalUrl = import.meta.env.VITE_MODAL_URL as string

  const [message, setMessage] = useState("")
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [gapiLoaded, setGapiLoaded] = useState(false)
  const [gisLoaded, setGisLoaded] = useState(false)
  const [tokenClient, setTokenClient] = useState<any>(null)
  const [authorized, setAuthorized] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Load Google scripts
  useEffect(() => {
    const gapiScript = document.createElement("script")
    gapiScript.src = "https://apis.google.com/js/api.js"
    gapiScript.async = true
    gapiScript.defer = true
    gapiScript.onload = () => window.gapi.load("client", initializeGapiClient)
    document.body.appendChild(gapiScript)

    const gisScript = document.createElement("script")
    gisScript.src = "https://accounts.google.com/gsi/client"
    gisScript.async = true
    gisScript.defer = true
    gisScript.onload = gisLoadedCallback
    document.body.appendChild(gisScript)

    return () => {
      document.body.removeChild(gapiScript)
      document.body.removeChild(gisScript)
    }
  }, [])

  const initializeGapiClient = async () => {
    try {
      await window.gapi.client.init({ apiKey: API_KEY })
      setGapiLoaded(true)
    } catch (error) {
      console.error("Error initializing GAPI client:", error)
    }
  }

  const gisLoadedCallback = () => {
    const client = window.google.accounts.oauth2.initTokenClient({
      client_id: CLIENT_ID,
      scope: SCOPES,
      callback: "",
    })
    setTokenClient(client)
    setGisLoaded(true)
  }

  // Fetch chat history on mount
  useEffect(() => {
    fetchChatHistory()
  }, [])

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [chatHistory])

  const fetchChatHistory = async () => {
    try {
      const response = await fetch(`${modalUrl}/agent/history`)
      if (!response.ok) return
      const data = await response.json()
      setChatHistory(data.messages)
    } catch (err) {
      console.error("Failed to fetch chat history:", err)
    }
  }

  const handleAuthClick = () => {
    if (!tokenClient) return
    tokenClient.callback = async (resp: any) => {
      if (resp.error) return
      try {
        await fetch(`${modalUrl}/auth/google/token`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ access_token: resp.access_token }),
        })
        setAuthorized(true)
      } catch (err) {
        console.error("Error exchanging token:", err)
      }
    }
    tokenClient.requestAccessToken({ prompt: "consent" })
  }

  const handleSignoutClick = () => {
    const token = window.gapi.client.getToken()
    if (token !== null) {
      window.google.accounts.oauth2.revoke(token.access_token)
      window.gapi.client.setToken("")
      setAuthorized(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    if (!message.trim()) return
    setIsLoading(true)
    const userMessage = { role: "user", text: message }
    setChatHistory((prev) => [...prev, userMessage])
    setMessage("")
    try {
      const response = await fetch(`${modalUrl}/agent/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMessage.text }),
      })
      if (!response.ok) throw new Error("Failed to get agent response")
      const data = await response.json()
      setChatHistory((prev) => [...prev, { role: "assistant", text: data.response }])
    } catch (err) {
      console.error("Error:", err)
    } finally {
      setIsLoading(false)
    }
  }

  const handleResetThread = async () => {
    try {
      await fetch(`${modalUrl}/agent/thread`, { method: "DELETE" })
      setChatHistory([])
    } catch (err) {
      console.error("Failed to reset thread:", err)
    }
  }

  const MessageBubble = ({ message }: { message: ChatMessage }) => {
    const isUser = message.role === "user"
    return (
      <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
        <div className={`max-w-xl p-3 rounded-lg text-sm ${isUser ? "bg-blue-600 text-white rounded-br-none" : "bg-gray-100 text-gray-900 rounded-bl-none"}`}>
          <Markdown>{message.text}</Markdown>
        </div>
      </div>
    )
  }

  return (
    <div className="container mx-auto p-4 max-w-4xl">
      <Card>
        <CardContent className="pt-6">
          {/* Header */}
          <div className="flex justify-between items-center mb-6">
            <h1 className="text-2xl font-bold">Executive Assistant</h1>
            <div className="flex gap-2">
              {!authorized ? (
                <Button
                  onClick={handleAuthClick}
                  disabled={!gapiLoaded || !gisLoaded}
                  className="flex items-center gap-2"
                >
                  <Calendar className="w-4 h-4" /> Connect Google
                </Button>
              ) : (
                <Button
                  onClick={handleSignoutClick}
                  variant="outline"
                  className="flex items-center gap-2"
                >
                  <LogOut className="w-4 h-4" /> Disconnect
                </Button>
              )}
            </div>
          </div>

          {/* Chat history */}
          <div className="h-[500px] overflow-y-auto pr-2 mb-4 border rounded-lg p-4">
            {chatHistory.length === 0 && (
              <p className="text-gray-400 text-center mt-10">
                Connect your Google account and start chatting!
              </p>
            )}
            {chatHistory.map((msg, idx) => (
              <MessageBubble key={idx} message={msg} />
            ))}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <form onSubmit={handleSubmit} className="flex gap-2">
            <input
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Ask your assistant anything..."
              className="flex-1 border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={isLoading}
            />
            <Button type="submit" disabled={isLoading || !message.trim()}>
              {isLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </Button>
          </form>

          {/* Reset */}
          <div className="flex justify-end mt-3">
            <Button onClick={handleResetThread} variant="outline" className="text-sm">
              Reset Thread
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export default App