from typing import Annotated

from pydantic import Field

from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.wikijs_client import graphql

_GET_PAGE_QUERY = """
query($id: Int!) {
  pages {
    single(id: $id) {
      id
      path
      title
      description
      content
      render
      contentType
      isPublished
      locale
      createdAt
      updatedAt
      tags { tag }
      author { name email }
    }
  }
}
"""

_CREATE_PAGE_MUTATION = """
mutation(
  $content: String!
  $description: String!
  $editor: String!
  $isPrivate: Boolean!
  $isPublished: Boolean!
  $locale: String!
  $path: String!
  $tags: [String]!
  $title: String!
) {
  pages {
    create(
      content: $content
      description: $description
      editor: $editor
      isPrivate: $isPrivate
      isPublished: $isPublished
      locale: $locale
      path: $path
      tags: $tags
      title: $title
    ) {
      responseResult { succeeded errorCode slug message }
      page { id path title }
    }
  }
}
"""

_UPDATE_PAGE_MUTATION = """
mutation(
  $id: Int!
  $content: String
  $description: String
  $isPublished: Boolean
  $locale: String
  $path: String
  $tags: [String]
  $title: String
  $editor: String
) {
  pages {
    update(
      id: $id
      content: $content
      description: $description
      isPublished: $isPublished
      locale: $locale
      path: $path
      tags: $tags
      title: $title
      editor: $editor
    ) {
      responseResult { succeeded errorCode slug message }
    }
  }
}
"""


@mcp.tool(description="Retrieve the full content of a Wiki.js page by its numeric ID.")
async def wikijs_get_page(
    page_id: Annotated[int, Field(description="Numeric ID of the page")],
) -> dict:
    async with trace_tool("wikijs_get_page", inputs={"page_id": page_id}):
        data = await graphql(_GET_PAGE_QUERY, {"id": page_id})
        page = data.get("pages", {}).get("single")
        if page is None:
            raise ValueError(f"Page {page_id} not found")
        return page


@mcp.tool(description="Create a new Wiki.js page with the given title, path and markdown content.")
async def wikijs_create_page(
    title: Annotated[str, Field(description="Page title")],
    path: Annotated[str, Field(description="URL path for the page, e.g. 'docs/getting-started'")],
    content: Annotated[str, Field(description="Page content in markdown")],
    description: Annotated[str, Field(description="Short description or excerpt")] = "",
    locale: Annotated[str, Field(description="Locale code, e.g. 'en' or 'fr'")] = "en",
    tags: Annotated[list[str], Field(description="List of tags")] = [],
    editor: Annotated[str, Field(description="Editor type: 'markdown' or 'wysiwyg'")] = "markdown",
    is_published: Annotated[bool, Field(description="Whether to publish immediately")] = True,
    is_private: Annotated[bool, Field(description="Whether the page is private")] = False,
) -> dict:
    async with trace_tool("wikijs_create_page", inputs={"title": title, "path": path}):
        data = await graphql(
            _CREATE_PAGE_MUTATION,
            {
                "title": title,
                "path": path,
                "content": content,
                "description": description,
                "locale": locale,
                "tags": tags,
                "editor": editor,
                "isPublished": is_published,
                "isPrivate": is_private,
            },
        )
        result = data.get("pages", {}).get("create", {})
        response = result.get("responseResult", {})
        page = result.get("page", {})
        return {
            "succeeded": response.get("succeeded", False),
            "message": response.get("message", ""),
            "id": page.get("id"),
            "path": page.get("path"),
            "title": page.get("title"),
        }


@mcp.tool(description="Update an existing Wiki.js page. Only the fields you provide will be changed.")
async def wikijs_update_page(
    page_id: Annotated[int, Field(description="Numeric ID of the page to update")],
    content: Annotated[str | None, Field(description="New markdown content")] = None,
    title: Annotated[str | None, Field(description="New title")] = None,
    description: Annotated[str | None, Field(description="New short description")] = None,
    tags: Annotated[list[str] | None, Field(description="New tag list (replaces existing tags)")] = None,
    is_published: Annotated[bool | None, Field(description="Change published state")] = None,
    locale: Annotated[str | None, Field(description="New locale code")] = None,
    path: Annotated[str | None, Field(description="New URL path")] = None,
    editor: Annotated[str | None, Field(description="Editor type if changing: 'markdown' or 'wysiwyg'")] = None,
) -> dict:
    async with trace_tool("wikijs_update_page", inputs={"page_id": page_id}):
        variables: dict = {"id": page_id}
        if content is not None:
            variables["content"] = content
        if title is not None:
            variables["title"] = title
        if description is not None:
            variables["description"] = description
        if tags is not None:
            variables["tags"] = tags
        if is_published is not None:
            variables["isPublished"] = is_published
        if locale is not None:
            variables["locale"] = locale
        if path is not None:
            variables["path"] = path
        if editor is not None:
            variables["editor"] = editor

        data = await graphql(_UPDATE_PAGE_MUTATION, variables)
        response = data.get("pages", {}).get("update", {}).get("responseResult", {})
        return {
            "succeeded": response.get("succeeded", False),
            "message": response.get("message", ""),
        }
