use derive_more::{Display, Error, From};
use regex::Regex;
use rust_decimal::prelude::*;
use std::collections::HashMap;
use std::fmt;
use std::io::BufRead;
use std::ptr;

use crate::error::*;
use crate::money::*;
use crate::tags::*;

const NAME_SEPARATOR: &str = ":";

#[derive(Debug, Display, Error, From)]
#[display(fmt = "invalid account name: {:?}", name)]
#[from(forward)]
pub struct InvalidAccountNameError {
    name: Box<str>,
}

#[derive(Debug, Display, Error, From)]
#[display(fmt = "duplicate account name: {:?}", name)]
#[from(forward)]
pub struct DuplicateAccountNameError {
    name: Box<str>,
}

#[derive(Debug)]
pub struct Account {
    name: Box<str>,
    currency: &'static Currency,
    parent: *const Account,
    children: Vec<Box<Account>>, // Box guarantees stable address for unsafe parent ptr
    labels: Labels,
    tags: Tags,
}

impl Account {
    fn validate_name(name: &str) -> std::result::Result<(), InvalidAccountNameError> {
        if name.is_empty()
            || name.contains(NAME_SEPARATOR)
            || name.contains("  ")
            || name.starts_with(" ")
            || name.ends_with(" ")
        {
            Err(InvalidAccountNameError::from(name))?;
        }
        Ok(())
    }

    fn new<'b, T: Iterator<Item = &'b str>>(name: &'b str, labels: T, tags: T) -> Result<Account> {
        Self::validate_name(name)?;
        Ok(Account {
            name: name.to_string().into_boxed_str(),
            currency: DEFAULT_CURRENCY,
            children: vec![],
            parent: ptr::null(),
            labels: Labels::from_iter(labels)?,
            tags: Tags::from_iter(tags)?,
        })
    }

    pub fn parent(&self) -> Option<&Account> {
        if self.parent.is_null() {
            None
        } else {
            Some(unsafe { &*self.parent })
        }
    }

    #[allow(dead_code)]
    pub fn self_and_all_parents(&self) -> AncestryIter {
        AncestryIter::new(Some(self))
    }

    #[allow(dead_code)]
    pub fn all_parents(&self) -> AncestryIter {
        AncestryIter::new(self.parent())
    }

    #[allow(dead_code)]
    pub fn contains(&self, other: &Self) -> bool {
        !other.self_and_all_parents().find(|&a| self == a).is_none()
    }

    pub fn bare_name(&self) -> String {
        self.name.to_string()
    }

    pub fn all_names(&self) -> NameGeneratorIter<'_> {
        NameGeneratorIter::new(self)
    }

    pub fn full_name(&self) -> String {
        (if let Some(p) = self.parent() {
            p.full_name() + NAME_SEPARATOR
        } else {
            "".to_string()
        }) + &*self.name
    }

    #[allow(dead_code)]
    pub fn relative_name(&self, other: &Account) -> Option<String> {
        let other_line = other.self_and_all_parents().collect::<Vec<&Account>>();
        if other_line.contains(&self) {
            return None;
        }
        let mut names = vec![&*self.name];
        for acc in self.all_parents() {
            if other_line.contains(&acc) {
                break;
            }
            names.push(&*acc.name);
        }
        names.reverse();
        Some(names.join(NAME_SEPARATOR))
    }

    #[allow(dead_code)]
    pub fn iter_labels(&self) -> impl Iterator<Item = &str> {
        self.labels.iter()
    }

    #[allow(dead_code)]
    pub fn iter_tags(&self) -> impl Iterator<Item = &str> {
        self.tags.iter()
    }

    pub fn money_from_decimal(&self, amount: Decimal) -> Money {
        Money::from_decimal(amount, self.currency)
    }

    pub fn money_from_str(&self, text: &str) -> std::result::Result<Money, MoneyError> {
        Money::from_str(text, self.currency)
    }

    fn add_child<'a, 'b, T: Iterator<Item = &'b str>>(
        &mut self,
        name: &'b str,
        labels: T,
        tags: T,
    ) -> Result<&mut Account> {
        let mut acc = Self::new(name, labels, tags)?;
        acc.parent = self;
        self.children.push(Box::new(acc));
        Ok(self.children.last_mut().unwrap())
    }

    #[allow(dead_code)]
    fn get_child(&self, name: &str) -> Option<&Account> {
        match self.children.iter().find(|&a| *a.name == *name) {
            Some(acc) => Some(&*acc),
            None => None,
        }
    }

    #[allow(dead_code)]
    pub fn is_parent(&self) -> bool {
        !self.children.is_empty()
    }

    fn traverse<E>(
        &self,
        f: &mut impl FnMut(&Account) -> std::result::Result<(), E>,
    ) -> std::result::Result<(), E> {
        f(self)?;
        for acc in self.children.iter() {
            acc.traverse(f)?;
        }
        Ok(())
    }
}

impl Eq for Account {}

impl PartialEq for Account {
    fn eq(&self, other: &Self) -> bool {
        self.name == other.name && self.parent == other.parent
    }
}

impl std::hash::Hash for Account {
    fn hash<H: std::hash::Hasher>(&self, state: &mut H) {
        self.name.hash(state);
        self.parent.hash(state);
    }
}

impl fmt::Display for Account {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.full_name())
    }
}

pub struct AncestryIter<'a> {
    account: Option<&'a Account>,
}

impl<'a> AncestryIter<'a> {
    fn new(account: Option<&'a Account>) -> AncestryIter<'a> {
        Self { account: account }
    }
}

impl<'a> Iterator for AncestryIter<'a> {
    type Item = &'a Account;

    fn next(&mut self) -> Option<Self::Item> {
        let ret = self.account;
        if !self.account.is_none() {
            self.account = self.account.unwrap().parent();
        }
        ret
    }
}

enum NameGeneratorState<'a> {
    Label(Vec<&'a str>),
    Name,
    Parent(Box<NameGeneratorIter<'a>>),
    Done,
}

pub struct NameGeneratorIter<'a> {
    account: &'a Account,
    state: NameGeneratorState<'a>,
}

impl<'a> NameGeneratorIter<'a> {
    fn new(account: &'a Account) -> NameGeneratorIter<'a> {
        Self {
            account: account,
            state: NameGeneratorState::Label(account.labels.iter().collect()),
        }
    }
}

impl Iterator for NameGeneratorIter<'_> {
    type Item = String;

    fn next(&mut self) -> Option<Self::Item> {
        loop {
            use NameGeneratorState::*;
            match &mut self.state {
                Label(vec) => {
                    if let Some(label) = vec.pop() {
                        return Some(label.to_string());
                    }
                    self.state = if let Some(p) = self.account.parent() {
                        Parent(Box::new(p.all_names()))
                    } else {
                        Name
                    };
                }
                Name => {
                    self.state = Done;
                    return Some(self.account.bare_name());
                }
                Parent(iter) => {
                    if let Some(pname) = iter.next() {
                        return Some(pname + NAME_SEPARATOR + &*self.account.name);
                    }
                    self.state = Done;
                }
                Done => break,
            }
        }
        None
    }
}

#[derive(Debug)]
pub struct Chart {
    top_level: Vec<Box<Account>>,
    index: HashMap<Box<str>, *const Account>,
}

pub struct ChartAccountContext<'c> {
    chart: &'c mut Chart,
    account: *mut Account,
}

lazy_static! {
    static ref LABEL_RE: Regex = Regex::new(r"\[([^]]+)]").unwrap();
    static ref TAG_RE: Regex = Regex::new(r"=([^=\s]+)").unwrap();
}

impl<'c> Chart {
    pub fn new() -> Chart {
        Chart {
            top_level: vec![],
            index: HashMap::default(),
        }
    }

    pub fn get_account(&self, name: &str) -> Option<&Account> {
        match self.index.get(name) {
            None => None,
            Some(ptr) => Some(unsafe { &**ptr }),
        }
    }

    fn traverse<E>(
        &self,
        f: &mut impl FnMut(&Account) -> std::result::Result<(), E>,
    ) -> std::result::Result<(), E> {
        for acc in &self.top_level {
            acc.traverse(f)?
        }
        Ok(())
    }

    fn get_last_account(&mut self, depth: usize) -> ChartAccountContext {
        let mut accounts: &mut Vec<Box<Account>> = &mut self.top_level;
        for _level in 0..depth {
            accounts = &mut accounts.last_mut().unwrap().children;
        }
        let ptr: *mut Account = &mut **accounts.last_mut().unwrap();
        ChartAccountContext {
            chart: self,
            account: ptr,
        }
    }

    fn add_account_to_index(&'c mut self, account: &'c mut Account) -> Result<()> {
        for name in account.all_names() {
            if !self
                .index
                .insert(name.clone().into_boxed_str(), account)
                .is_none()
            {
                Err(DuplicateAccountNameError::from(name))?;
            }
        }
        Ok(())
    }

    pub fn add_top_level_account<'b, T: Iterator<Item = &'b str>>(
        &'c mut self,
        name: &'b str,
        labels: T,
        tags: T,
    ) -> Result<ChartAccountContext<'c>> {
        let mut acc = Box::new(Account::new(name, labels, tags)?);
        self.add_account_to_index(&mut *acc)?;
        let ptr: *mut Account = &mut *acc;
        self.top_level.push(acc);
        Ok(ChartAccountContext {
            chart: self,
            account: ptr,
        })
    }

    pub fn add_child_account<'b, T: Iterator<Item = &'b str>>(
        &'c mut self,
        parent: &'c mut Account,
        name: &'b str,
        labels: T,
        tags: T,
    ) -> Result<ChartAccountContext<'c>> {
        let acc = parent.add_child(name, labels, tags)?;
        self.add_account_to_index(acc)?;
        Ok(ChartAccountContext {
            chart: self,
            account: acc,
        })
    }

    fn extract_matches<'a>(text: &'a str, rexp: &Regex) -> (String, Vec<&'a str>) {
        let mut ret_str = "".to_string();
        let mut ret_vec = vec![];
        let mut end: usize = 0;
        let mut grow = |frag: &str| {
            let tfrag = frag.trim();
            if !tfrag.is_empty() {
                if !ret_str.is_empty() {
                    ret_str += " ";
                }
                ret_str += tfrag;
            }
        };
        for cap in rexp.captures_iter(&text) {
            ret_vec.push(cap.get(1).unwrap().as_str());
            let all = cap.get(0).unwrap();
            grow(&text[end..all.start()]);
            end = all.end();
        }
        grow(&text[end..]);
        (ret_str, ret_vec)
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
        struct Level {
            indent: Box<str>,
        }
        let mut stack: Vec<Level> = vec![];
        let mut read_line = |result: std::result::Result<String, std::io::Error>| -> Result<()> {
            let line = result?;
            let text = line.trim_start();
            if text.starts_with("#") || text.is_empty() {
                return Ok(());
            }
            let indent = &line[..(line.len() - text.len())];
            while !stack.is_empty() && stack.last().unwrap().indent.starts_with(indent) {
                stack.pop();
            }
            if !if stack.is_empty() {
                indent.is_empty()
            } else {
                indent.starts_with(&*stack.last().unwrap().indent)
            } {
                Err(std::io::Error::new(
                    std::io::ErrorKind::InvalidInput,
                    "bad indent",
                ))?;
            }
            let (name1, tags) = Chart::extract_matches(text, &TAG_RE);
            let (name, labels) = Chart::extract_matches(&name1, &LABEL_RE);
            if stack.is_empty() {
                self.add_top_level_account(&name, labels.into_iter(), tags.into_iter())?;
            } else {
                self.get_last_account(stack.len() - 1).add_child(
                    &name,
                    labels.into_iter(),
                    tags.into_iter(),
                )?;
            };
            stack.push(Level {
                indent: indent.to_string().into_boxed_str(),
            });
            Ok(())
        };
        let mut line_number: u32 = 0;
        for result in std::io::BufReader::new(reader).lines() {
            line_number += 1;
            read_line(result).map_err(|err| InputError::new(InputLoc::new(line_number), err))?;
        }
        Ok(())
    }

    #[allow(dead_code)]
    pub fn write_to<W: std::io::Write>(&self, writer: &mut W) -> Result<()> {
        self.traverse(&mut |acc| writeln!(writer, "{}{}{}", acc, acc.labels, acc.tags))?;
        Ok(())
    }
}

impl<'c> ChartAccountContext<'c> {
    pub fn add_child<'a, 'b, T: Iterator<Item = &'b str>>(
        &'c mut self,
        name: &'b str,
        labels: T,
        tags: T,
    ) -> Result<ChartAccountContext<'c>> {
        self.chart
            .add_child_account(unsafe { &mut *self.account }, name, labels, tags)
    }
}

#[cfg(test)]
mod tests {
    use crate::error::*;
    use crate::Account;
    use crate::Chart;
    use itertools::sorted;
    use std::collections::HashSet;
    use stringreader::StringReader;

    #[test]
    fn account() -> Result<()> {
        let mut a = Account::new("Able", vec!["a"].into_iter(), vec![].into_iter())?;
        let b = a.add_child("Baker", vec!["b"].into_iter(), vec!["x"].into_iter())?;
        let c = b.add_child(
            "Charlie",
            vec!["c", "C"].into_iter(), // labels
            vec!["y", "z"].into_iter(), // tags
        )?;

        println!("{:?}", c);
        assert!(!c.is_parent());
        assert_eq!(c.bare_name(), "Charlie");
        assert_eq!(c.full_name(), "Able:Baker:Charlie");
        assert_eq!(
            sorted(c.all_names()).collect::<Vec<String>>(),
            vec![
                "Able:Baker:Charlie",
                "C",
                "a:Baker:Charlie",
                "b:Charlie",
                "c",
            ]
        );
        assert_eq!(
            sorted(c.iter_labels()).collect::<Vec<&str>>(),
            vec!["C", "c"]
        );
        assert_eq!(sorted(c.iter_tags()).collect::<Vec<&str>>(), vec!["y", "z"]);
        Ok(())
    }

    #[test]
    fn chart() -> Result<()> {
        let mut chart = Chart::new();
        chart.read_from(StringReader::new(
            r"
Able [a] [A] =x
    Baker [b] =y
        Charlie [c] =z
    Delta [d] =z
        Echo [E] [e]
",
        ))?;
        let a = chart.get_account("a").ok_or(Fail::from("a"))?;
        let b = chart.get_account("b").ok_or(Fail::from("b"))?;
        let c = chart.get_account("c").ok_or(Fail::from("c"))?;
        let d = chart.get_account("d").ok_or(Fail::from("d"))?;
        let e = chart.get_account("e").ok_or(Fail::from("e"))?;

        assert_eq!(chart.get_account("Able"), Some(a));
        assert_eq!(chart.get_account("Baker"), None);
        assert_eq!(chart.get_account("Charlie"), None);
        assert_eq!(chart.get_account("Delta"), None);
        assert_eq!(chart.get_account("Echo"), None);
        assert_eq!(chart.get_account("A"), Some(a));
        assert_eq!(chart.get_account("Able:Baker"), Some(b));
        assert_eq!(chart.get_account("a:Baker"), Some(b));
        assert_eq!(chart.get_account("A:Baker"), Some(b));
        assert_eq!(chart.get_account("Able:Baker:Charlie"), Some(c));
        assert_eq!(chart.get_account("a:Baker:Charlie"), Some(c));
        assert_eq!(chart.get_account("A:Baker:Charlie"), Some(c));
        assert_eq!(chart.get_account("b:Charlie"), Some(c));
        assert_eq!(chart.get_account("Able:Delta"), Some(d));
        assert_eq!(chart.get_account("Able:Delta:Echo"), Some(e));
        assert_eq!(chart.get_account("E"), Some(e));

        assert_eq!(a.full_name(), "Able");
        assert_eq!(b.full_name(), "Able:Baker");
        assert_eq!(c.full_name(), "Able:Baker:Charlie");
        assert_eq!(d.full_name(), "Able:Delta");
        assert_eq!(e.full_name(), "Able:Delta:Echo");

        assert!(a.is_parent());
        assert!(b.is_parent());
        assert!(!c.is_parent());
        assert!(d.is_parent());
        assert!(!e.is_parent());

        assert!(a.contains(a));
        assert!(a.contains(b));
        assert!(a.contains(c));
        assert!(b.contains(c));
        assert!(c.contains(c));
        assert!(!b.contains(a));
        assert!(!c.contains(a));
        assert!(!c.contains(b));
        assert!(!c.contains(e));
        assert!(!e.contains(c));

        assert_eq!(c.relative_name(a), Some("Baker:Charlie".to_string()));
        assert_eq!(c.relative_name(b), Some("Charlie".to_string()));
        assert_eq!(c.relative_name(c), None);
        assert_eq!(b.relative_name(c), None);
        assert_eq!(c.relative_name(d), Some("Baker:Charlie".to_string()));
        assert_eq!(c.relative_name(e), Some("Baker:Charlie".to_string()));

        let hs = HashSet::<&Account>::from([a, c, d]);
        assert!(hs.contains(a));
        assert!(!hs.contains(b));
        assert!(hs.contains(c));
        assert!(hs.contains(d));
        assert!(!hs.contains(e));

        Ok(())
    }
}
