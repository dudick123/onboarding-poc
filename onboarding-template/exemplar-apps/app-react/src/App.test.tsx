import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import App from './App'

describe('App', () => {
  it('renders the hello world heading', () => {
    render(<App />)
    expect(screen.getByRole('heading', { name: /hello, world!/i })).toBeDefined()
  })

  it('renders the starter description', () => {
    render(<App />)
    expect(screen.getByText(/react 18 \+ vite starter/i)).toBeDefined()
  })
})
