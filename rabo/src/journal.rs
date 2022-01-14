use std::io::BufRead;

use crate::account::*;
use crate::error::*;
use crate::transaction::*;

pub struct Journal<'c> {
    #[allow(dead_code)]
    chart: &'c Chart,
    pub transactions: Vec<Transaction<'c>>,
}

#[derive(Debug)]
struct Line {
    text: Box<str>,
    #[allow(dead_code)]
    loc: InputLoc,
}

struct LineIter<B: BufRead> {
    lines: std::io::Lines<B>,
    line_number: u32,
}

impl<B: BufRead> LineIter<B> {
    fn new(lines: std::io::Lines<B>) -> LineIter<B> {
        LineIter {
            lines,
            line_number: 0,
        }
    }
}

impl<B: BufRead> Iterator for LineIter<B> {
    type Item = std::result::Result<Line, InputError>;

    fn next(&mut self) -> Option<Self::Item> {
        if let Some(result) = self.lines.next() {
            match result {
                Ok(text) => {
                    self.line_number += 1;
                    return Some(Ok(Line {
                        text: text.into_boxed_str(),
                        loc: InputLoc::new(self.line_number),
                    }));
                }
                Err(err) => {
                    return Some(Err(InputError::new(
                        InputLoc::new(self.line_number),
                        Box::new(err),
                    )))
                }
            }
        }
        None
    }
}

#[derive(Debug)]
struct Block {
    lines: Vec<Line>,
}

struct BlockIter<B: BufRead> {
    line_iter: LineIter<B>,
}

impl<B: BufRead> BlockIter<B> {
    fn new(lines: std::io::Lines<B>) -> BlockIter<B> {
        BlockIter {
            line_iter: LineIter::new(lines),
        }
    }
}

impl<B: BufRead> Iterator for BlockIter<B> {
    type Item = std::result::Result<Block, InputError>;

    fn next(&mut self) -> Option<Self::Item> {
        let mut block = Block { lines: vec![] };
        while let Some(result) = self.line_iter.next() {
            match result {
                Ok(line) => {
                    if line.text.starts_with("#") {
                        // ignore comment lines
                    } else if !line.text.trim().is_empty() {
                        block.lines.push(line);
                    } else if !block.lines.is_empty() {
                        break;
                    }
                }
                Err(err) => return Some(Err(err)),
            }
        }
        if !block.lines.is_empty() {
            Some(Ok(block))
        } else {
            None
        }
    }
}

impl<'c> Journal<'c> {
    pub fn new(chart: &'c Chart) -> Journal<'c> {
        Journal {
            chart,
            transactions: vec![],
        }
    }

    pub fn read_from_path(&mut self, path: &str) -> Result<()> {
        if let Err(mut err) = self.read_from(std::fs::File::open(path)?) {
            err.set_path(path);
            Err(err)?;
        }
        Ok(())
    }

    pub fn read_from<R: std::io::Read>(
        &mut self,
        reader: R,
    ) -> std::result::Result<(), InputError> {
        let blocks = BlockIter::new(std::io::BufReader::new(reader).lines());
        for block in blocks {
            println!("{:?}", block);
        }
        Ok(())
    }
}
