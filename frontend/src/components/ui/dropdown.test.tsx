import * as React from 'react'
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { describe, expect, it, vi } from 'vitest'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from './dropdown'

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

describe('DropdownMenuContent', () => {
  it('does not bubble a menu item click to a clickable React ancestor such as a table row', () => {
    const container = document.createElement('div')
    document.body.appendChild(container)
    const root: Root = createRoot(container)
    const onRowClick = vi.fn()

    act(() => {
      root.render(
        <div onClick={onRowClick}>
          <DropdownMenu defaultOpen>
            <DropdownMenuTrigger>Open menu</DropdownMenuTrigger>
            <DropdownMenuContent>
              <DropdownMenuItem>Delete pipeline</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>,
      )
    })

    const item = Array.from(document.querySelectorAll('[role="menuitem"]')).find((element) =>
      element.textContent?.includes('Delete pipeline'),
    )
    expect(item).toBeTruthy()

    act(() => {
      item!.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    })

    expect(onRowClick).not.toHaveBeenCalled()

    act(() => root.unmount())
    container.remove()
  })
})
