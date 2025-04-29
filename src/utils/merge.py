import re
from collections import deque
from dataclasses import dataclass
from typing import List, Optional, Tuple
from dataclasses import replace


def merge(content: str, changes: str) -> str:
    """
    Merge changes with content.

    Changes comprises of multiple change hunks corresponding to change in a single part
    of the content.

    A change chunk starts with either @UPDATE or @DELETE.
    - @UPDATE is used for updating existing content
    - @DELETE is used for deleting existing content

    An @UPDATE chunk must have a @@BEFORE and @@AFTER section.
    - The @@BEFORE section contains the existing content that needs to be replaced.
    - The @@AFTER section contains the new content that will replace the existing content.

    Args:
        content: The original content as a string
        changes: The changes to apply

    Returns:
        The merged content as a string
    """
    content = content.split("\n")
    changes = changes.split("\n")
    chunks = parse_chunks(changes)
    chunks = invalidate_mismatched_ranges(content, chunks)
    chunks = correct_chunks(content, chunks)
    chunks = sort_and_validate_chunk_order(chunks)
    updated_content = apply_changes(content, chunks)
    return "\n".join(updated_content)


@dataclass
class Chunk:
    raw_chunk: list[str]
    curr_content: list[str]
    new_content: list[str]
    curr_range: Optional[tuple[int, int]]


@dataclass
class RawChunk:
    start_index: int
    end_index: int
    op_type: str
    lines: deque[str]


def is_empty_line(line: str) -> bool:
    return line.strip() == ""


def generate_snippet(
    content: list[str], from_idx: int, to_idx: Optional[int] = None
) -> str:
    to_idx = to_idx or from_idx
    num_context_lines = 3
    before = content[max(0, from_idx - num_context_lines) : from_idx]
    middle = content[from_idx : to_idx + 1]
    after = content[to_idx + 1 : min(len(content), to_idx + num_context_lines + 1)]
    return "\n".join(
        ["  " + line for line in before]
        + ["> " + line for line in middle]
        + ["  " + line for line in after]
    )


def parse_chunks(changes: list[str]) -> list[Chunk]:
    # Split into raw diff chunks
    raw_chunks: List[RawChunk] = []
    for idx, line in enumerate(changes):
        op_match = re.search(r"^@\s*(UPDATE|DELETE)\s?", line.strip(), re.IGNORECASE)
        if op_match:
            raw_chunks.append(
                RawChunk(
                    start_index=idx,
                    end_index=idx,
                    op_type=op_match.group(1).upper(),
                    lines=deque([]),
                )
            )
            continue

        # Validate that there is no non-empty line not associated with any chunk
        if not raw_chunks:
            if not is_empty_line(line):
                raise ValueError(
                    f"Found a line that is not associated with an operation: {line}\n"
                    + generate_snippet(changes, idx)
                )
            else:
                continue

        if raw_chunks[-1].op_type == "UPDATE":
            # Skip empty lines right after @UPDATE
            if len(raw_chunks[-1].lines) == 0 and is_empty_line(line):
                continue
            # Split different BEFORE sections in an UPDATE chunk into a separate chunk
            if len(raw_chunks[-1].lines) > 0 and re.search(
                r"^@@\s*(BEFORE)\s?", line.strip(), re.IGNORECASE
            ):
                raw_chunks[-1].end_index = idx - 1
                raw_chunks.append(
                    RawChunk(
                        start_index=idx,
                        end_index=idx,
                        op_type="UPDATE",
                        lines=deque([]),
                    )
                )

        raw_chunks[-1].end_index = idx
        raw_chunks[-1].lines.append(line)

    # Validate that all chunks are non-empty
    for raw_chunk in raw_chunks:
        if len(raw_chunk.lines) == 0:
            raise ValueError(
                f"Found an empty chunk\n"
                + generate_snippet(changes, raw_chunk.start_index)
            )

    # Actually build Chunk objects
    chunks: List[Chunk] = []
    for raw_chunk in raw_chunks:
        if raw_chunk.op_type == "DELETE":
            chunks.append(
                Chunk(
                    raw_chunk=list(raw_chunk.lines),
                    curr_content=list(raw_chunk.lines),
                    new_content=[],
                    curr_range=None,
                )
            )
            continue

        # raw_chunk.op_type == "UPDATE"
        # First line must be @@BEFORE
        if not re.search(
            r"^@@\s*(BEFORE)\s?", raw_chunk.lines[0].strip(), re.IGNORECASE
        ):
            raise ValueError(
                f"Invalid update chunk: {raw_chunk}. First line in an UPDATE chunk must be @@BEFORE.\n"
                + generate_snippet(changes, raw_chunk.start_index)
            )

        before = []
        idx = 1
        while idx < len(raw_chunk.lines) and not re.search(
            r"^@@\s*(AFTER)\s?", raw_chunk.lines[idx].strip(), re.IGNORECASE
        ):
            before.append(raw_chunk.lines[idx])
            idx += 1

        if idx == len(raw_chunk.lines):
            raise ValueError(
                f"Invalid update chunk: {raw_chunk}. UPDATE chunk must have @@AFTER section.\n"
                + generate_snippet(changes, raw_chunk.start_index, raw_chunk.end_index)
            )
        assert (
            re.search(r"^@@\s*(AFTER)\s?", raw_chunk.lines[idx].strip(), re.IGNORECASE)
            is not None
        )
        idx += 1

        after = []
        while idx < len(raw_chunk.lines):
            if re.search(
                r"^@@\s*(AFTER)\s?", raw_chunk.lines[idx].strip(), re.IGNORECASE
            ):
                raise ValueError(
                    f"Invalid UPDATE chunk: {raw_chunk}. UPDATE chunk cannot have multiple @@AFTER sections.\n"
                    + generate_snippet(
                        changes, raw_chunk.start_index, raw_chunk.end_index
                    )
                )
            after.append(raw_chunk.lines[idx])
            idx += 1
        chunks.append(
            Chunk(
                raw_chunk=list(raw_chunk.lines),
                curr_content=before,
                new_content=after,
                curr_range=None,
            )
        )

    # Clean line numbers and try to extract ranges from chunks
    return [canonicalize_line_numbers(chunk) for chunk in chunks]


def canonicalize_line_numbers(chunk: Chunk) -> Chunk:
    all_non_empty_lines = [
        line
        for line in (chunk.curr_content + chunk.new_content)
        if not is_empty_line(line)
    ]
    # all_have_line_numbers = all(re.search(r"^\d+:", line) is not None for line in all_non_empty_lines)
    # print(f"zzz - {all_non_empty_lines}, {all_have_line_numbers=}")
    # Either all non-empty lines must have line numbers or none
    if not all(re.search(r"^\d+:", line) is not None for line in all_non_empty_lines):
        return chunk

    # If all non-empty lines have line numbers then ignore the empty lines
    curr_content = [line for line in chunk.curr_content if not is_empty_line(line)]
    new_content = [line for line in chunk.new_content if not is_empty_line(line)]
    line_numbers = [
        # Convert line numbers to 0-based index
        int(line.split(":", maxsplit=1)[0]) - 1
        for line in curr_content
    ]
    chunk = replace(
        chunk,
        curr_content=[line.split(":", maxsplit=1)[1] for line in curr_content],
        new_content=[line.split(":", maxsplit=1)[1] for line in new_content],
    )

    # All line numbers in context must be continuous
    is_contiguous = all(
        line_numbers[i] == line_numbers[i - 1] + 1 for i in range(1, len(line_numbers))
    )
    if not is_contiguous:
        return chunk

    return replace(chunk, curr_range=(line_numbers[0], line_numbers[-1]))


def invalidate_mismatched_ranges(
    content: list[str], chunks: list[Chunk]
) -> list[Chunk]:
    """
    Invalidate ranges in chunks that do not match the content.
    """
    result: List[Chunk] = []

    for chunk in chunks:
        if chunk.curr_range is None:
            result.append(chunk)
            continue

        start, end = chunk.curr_range
        if start < 0 or end >= len(content):
            result.append(replace(chunk, curr_range=None))
            continue

        matches_content = True
        for i in range(start, end + 1):
            if content[i] != chunk.curr_content[i - start]:
                matches_content = False
                break

        if not matches_content:
            result.append(replace(chunk, curr_range=None))
            continue

        result.append(chunk)

    return result


def correct_chunks(content: list[str], chunks: list[Chunk]) -> list[Chunk]:
    return [
        correct_chunk(content, chunk) if chunk.curr_range is None else chunk
        for chunk in chunks
    ]


def correct_chunk(content: list[str], chunk: Chunk) -> Chunk:
    non_empty_content_lines = [
        (idx, line) for idx, line in enumerate(content) if line.strip()
    ]
    non_empty_context_lines = [
        (idx, line) for idx, line in enumerate(chunk.curr_content) if line.strip()
    ]
    if len(non_empty_content_lines) < len(non_empty_context_lines):
        raise ValueError(f"Invalid chunk: {chunk}")

    match = None
    for i in range(len(non_empty_content_lines) - len(non_empty_context_lines) + 1):
        is_match = True
        for j in range(len(non_empty_context_lines)):
            if (
                non_empty_content_lines[i + j][1].strip()
                != non_empty_context_lines[j][1].strip()
            ):
                is_match = False
                break
        if is_match:
            if match:
                raise ValueError(
                    f"Invalid chunk {chunk.raw_chunk}. "
                    + "Provided lines in chunk do not have accurate line numbers and match multiple parts of existing content"
                )
            match = (i, i + len(non_empty_context_lines) - 1)
            break

    if not match:
        raise ValueError(
            f"Invalid chunk {chunk.raw_chunk}. Provided lines in chunk do not match existing content."
        )

    return replace(
        chunk,
        curr_range=(
            non_empty_content_lines[match[0]][0],
            non_empty_content_lines[match[1]][0],
        ),
    )


def sort_and_validate_chunk_order(chunks: list[Chunk]) -> list[Chunk]:
    """
    Sort chunks by their current range and validate that they do not overlap.
    """
    result: List[Chunk] = sorted(chunks, key=lambda chunk: chunk.curr_range[0])
    for i in range(1, len(result)):
        if result[i].curr_range[0] <= result[i - 1].curr_range[1]:
            raise ValueError(f"Invalid chunk order: {result}")
    return result


def apply_changes(content: list[str], chunks: list[Chunk]) -> list[str]:
    """
    Apply changes to the content based on the provided chunks.
    """
    merged: List[str] = []

    curr_content_idx = 0
    for chunk in chunks:
        if chunk.curr_range[0] > curr_content_idx:
            merged.extend(content[curr_content_idx : chunk.curr_range[0]])
        merged.extend(chunk.new_content)
        curr_content_idx = chunk.curr_range[1] + 1

    if curr_content_idx < len(content):
        merged.extend(content[curr_content_idx:])

    return merged
