use rust_decimal::prelude::*;
use std::fmt;

use crate::money::*;
use crate::tags::*;

#[derive(Debug)]
struct AccountNode {
    name: Box<str>,
    currency: &'static Currency,
    children: Vec<usize>,
    tags: Tags,
}

#[derive(Debug)]
pub struct Chart {
    nodes: Vec<AccountNode>,
    top_level: Vec<usize>,
}

#[derive(Debug)]
pub struct Account<'c> {
    chart: &'c Chart,
    index: usize,
    parent: Option<usize>,
}

impl Chart {
    pub fn new() -> Chart {
        Chart {
            nodes: vec![],
            top_level: vec![],
        }
    }

    pub fn add_top_level_account<'b, T: Iterator<Item = &'b str>>(
        &mut self,
        name: &'b str,
        tags: T,
    ) -> Account {
        self.nodes.push(AccountNode::new(name, tags));
        let index = self.nodes.len() - 1;
        self.top_level.push(index);
        Account {
            chart: self,
            index,
            parent: None,
        }
    }

    pub fn add_child_account<'a, 'b, T: Iterator<Item = &'b str>>(
        &mut self,
        parent: &Account,
        name: &'b str,
        tags: T,
    ) -> Account {
        self.nodes.push(AccountNode::new(name, tags));
        let child_index = self.nodes.len() - 1;
        self.nodes[parent.index].children.push(child_index);
        Account {
            chart: self,
            index: child_index,
            parent: Some(parent.index),
        }
    }
}

impl AccountNode {
    fn new<'b, T: Iterator<Item = &'b str>>(name: &'b str, tags: T) -> AccountNode {
        assert!(!name.is_empty());
        AccountNode {
            name: name.to_string().into_boxed_str(),
            currency: DEFAULT_CURRENCY,
            children: vec![],
            tags: Tags::from_iter(tags),
        }
    }
}

impl<'c> Account<'c> {
    pub fn node(&self) -> &AccountNode {
        &self.chart.nodes[self.index]
    }

    pub fn money_from_decimal(&self, amount: Decimal) -> Money {
        Money::from_decimal(amount, self.node().currency)
    }

    pub fn money_from_str(&self, text: &str) -> Result<Money, MoneyError> {
        Money::from_str(text, self.node().currency)
    }
}

impl fmt::Display for Account<'_> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        if !self.parent.is_none() {
            write!(f, "{}:", self.parent.unwrap())?;
        }
        write!(f, "{}", self.node().name)
    }
}
